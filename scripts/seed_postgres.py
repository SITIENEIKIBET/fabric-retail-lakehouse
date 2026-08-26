"""
Seeds the retail_source Postgres database with synthetic data,
including deliberate data quality issues for later Silver-layer testing.

Usage:
    python scripts/seed_postgres.py
"""
import logging
import os
import random
import sys

import psycopg2
from dotenv import load_dotenv
from faker import Faker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()
fake = Faker()
Faker.seed(42)
random.seed(42)

REQUIRED_ENV_VARS = ["PG_HOST", "PG_PORT", "PG_DATABASE", "PG_USER", "POSTGRES_PASSWORD"]


def get_connection():
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        logger.error("Missing required environment variables: %s", missing)
        sys.exit(1)

    try:
        conn = psycopg2.connect(
            host=os.getenv("PG_HOST"),
            port=os.getenv("PG_PORT"),
            dbname=os.getenv("PG_DATABASE"),
            user=os.getenv("PG_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error("Failed to connect to Postgres: %s", e)
        sys.exit(1)


def seed_customers(cur, n=500):
    logger.info("Seeding %d customers...", n)
    inserted_ids = []
    for i in range(n):
        first = fake.first_name()
        last = fake.last_name()

        # Deliberate data quality issues (~8% of rows)
        email = fake.email()
        if random.random() < 0.05:
            email = None  # missing email
        if random.random() < 0.03:
            email = email.upper() if email else None  # inconsistent casing

        phone = fake.phone_number()
        if random.random() < 0.05:
            phone = phone.replace("-", "").replace(" ", "")  # inconsistent format

        cur.execute(
            """
            INSERT INTO customers (first_name, last_name, email, phone, city, country)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING customer_id;
            """,
            (first, last, email, phone, fake.city(), fake.country()),
        )
        inserted_ids.append(cur.fetchone()[0])

    # Inject a handful of exact duplicate customers (same email, different id)
    # to simulate a realistic dedup problem for the Silver layer.
    dup_sample = random.sample(inserted_ids, k=10)
    for cust_id in dup_sample:
        cur.execute(
            "SELECT first_name, last_name, email, phone, city, country FROM customers WHERE customer_id = %s",
            (cust_id,),
        )
        row = cur.fetchone()
        cur.execute(
            """
            INSERT INTO customers (first_name, last_name, email, phone, city, country)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            row,
        )

    logger.info("Customers seeded (including 10 intentional duplicates).")
    return inserted_ids


def seed_products(cur, n=100):
    logger.info("Seeding %d products...", n)
    categories = ["Electronics", "Home & Kitchen", "Apparel", "Books", "Toys", "Sports"]
    product_ids = []
    for _ in range(n):
        cur.execute(
            """
            INSERT INTO products (product_name, category, unit_price, is_active)
            VALUES (%s, %s, %s, %s)
            RETURNING product_id;
            """,
            (
                fake.catch_phrase(),
                random.choice(categories),
                round(random.uniform(5, 500), 2),
                random.random() > 0.05,  # ~5% inactive products
            ),
        )
        product_ids.append(cur.fetchone()[0])
    logger.info("Products seeded.")
    return product_ids


def seed_orders_and_items(cur, customer_ids, product_ids, n_orders=2000):
    logger.info("Seeding %d orders with line items...", n_orders)
    statuses = ["completed", "pending", "cancelled", "refunded"]
    max_valid_product_id = max(product_ids)

    for _ in range(n_orders):
        customer_id = random.choice(customer_ids)
        order_date = fake.date_time_between(start_date="-1y", end_date="now")
        status = random.choice(statuses)

        cur.execute(
            """
            INSERT INTO orders (customer_id, order_date, order_status)
            VALUES (%s, %s, %s)
            RETURNING order_id;
            """,
            (customer_id, order_date, status),
        )
        order_id = cur.fetchone()[0]

        n_items = random.randint(1, 5)
        for _ in range(n_items):
            product_id = random.choice(product_ids)

            # ~2% of line items reference a non-existent product_id
            # (simulates upstream referential integrity breakage)
            if random.random() < 0.02:
                product_id = max_valid_product_id + random.randint(100, 999)

            cur.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s);
                """,
                (order_id, product_id, random.randint(1, 4), round(random.uniform(5, 500), 2)),
            )

    logger.info("Orders and order items seeded.")


def main():
    conn = get_connection()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            customer_ids = seed_customers(cur)
            product_ids = seed_products(cur)
            seed_orders_and_items(cur, customer_ids, product_ids)
        conn.commit()
        logger.info("Seed completed successfully and committed.")
    except Exception as e:
        conn.rollback()
        logger.error("Seeding failed, transaction rolled back: %s", e)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()