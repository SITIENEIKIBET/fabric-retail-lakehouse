"""
Simulates a "Day 2" batch of changes against the retail_source Postgres
database, for demonstrating SCD Type 2 handling in the Gold layer.

Effects:
- 15 existing customers get their city changed (triggers SCD2 versioning)
- 10 brand new customers are inserted

Note: late-arriving order simulation is handled separately, downstream of
Postgres, via scripts/inject_late_arriving_orders.py — see ADR-005 for why.
Our orders.customer_id foreign key constraint correctly prevents inserting
an order for a non-existent customer directly into Postgres, so that part
of the scenario is simulated at the CSV export stage instead, representing
data arriving from a decoupled order-events source.

Usage:
    python scripts/simulate_day2_changes.py
"""
import logging
import os
import random
import sys

import psycopg2
from dotenv import load_dotenv
from faker import Faker

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
fake = Faker()
Faker.seed(99)
random.seed(99)

REQUIRED_ENV_VARS = ["PG_HOST", "PG_PORT", "PG_DATABASE", "PG_USER", "POSTGRES_PASSWORD"]


def get_connection():
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        logger.error("Missing required environment variables: %s", missing)
        sys.exit(1)

    try:
        return psycopg2.connect(
            host=os.getenv("PG_HOST"), port=os.getenv("PG_PORT"),
            dbname=os.getenv("PG_DATABASE"), user=os.getenv("PG_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
        )
    except psycopg2.OperationalError as e:
        logger.error("Failed to connect to Postgres: %s", e)
        sys.exit(1)


def update_existing_customers(cur, n=15):
    """Update city for the first n customers by id — triggers SCD2 versioning downstream."""
    cur.execute("SELECT customer_id FROM customers ORDER BY customer_id LIMIT %s", (n,))
    ids = [r[0] for r in cur.fetchall()]
    for cid in ids:
        new_city = fake.city()
        cur.execute(
            "UPDATE customers SET city = %s, updated_at = NOW() WHERE customer_id = %s",
            (new_city, cid),
        )
    logger.info("Updated city for %d existing customers (SCD2 trigger).", len(ids))
    return ids


def insert_new_customers(cur, n=10):
    """Insert n brand-new customers, simulating organic customer growth."""
    new_ids = []
    for _ in range(n):
        cur.execute(
            """
            INSERT INTO customers (first_name, last_name, email, phone, city, country)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING customer_id;
            """,
            (fake.first_name(), fake.last_name(), fake.email(), fake.phone_number(), fake.city(), fake.country()),
        )
        new_ids.append(cur.fetchone()[0])
    logger.info("Inserted %d brand-new customers.", len(new_ids))
    return new_ids


def main():
    conn = get_connection()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            updated_ids = update_existing_customers(cur)
            new_ids = insert_new_customers(cur)
        conn.commit()
        logger.info("Day 2 simulation committed successfully.")
        logger.info("Updated customer_ids (city changed): %s", updated_ids)
        logger.info("New customer_ids: %s", new_ids)
    except Exception as e:
        conn.rollback()
        logger.error("Day 2 simulation failed, rolled back: %s", e)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()