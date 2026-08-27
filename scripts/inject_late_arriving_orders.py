"""
Appends synthetic 'late-arriving' order records directly to the exported
orders.csv, simulating orders that arrived from a separate order-events
source not governed by the same referential integrity as the customer
master data (a realistic scenario in decoupled/microservice architectures).

These customer_ids deliberately do NOT exist in customers.csv / dim_customers,
demonstrating the late-arriving dimension problem in the Gold layer.
See ADR-005 for why this is injected here rather than into Postgres directly.

Usage:
    python scripts/inject_late_arriving_orders.py
"""
import csv
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ORDERS_CSV = "data/raw/postgres/orders.csv"
LATE_CUSTOMER_IDS = [9001, 9002, 9003]  # deliberately far outside any real customer_id range


def get_next_order_id() -> int:
    with open(ORDERS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        max_id = max(int(row["order_id"]) for row in reader)
    return max_id + 1


def append_late_orders():
    next_id = get_next_order_id()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(ORDERS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for i, cust_id in enumerate(LATE_CUSTOMER_IDS):
            writer.writerow([next_id + i, cust_id, now, "pending", now])

    logger.info(
        "Appended %d late-arriving orders (order_ids %d-%d) referencing "
        "customer_ids %s, which do NOT exist in customers.csv.",
        len(LATE_CUSTOMER_IDS), next_id, next_id + len(LATE_CUSTOMER_IDS) - 1, LATE_CUSTOMER_IDS,
    )


if __name__ == "__main__":
    append_late_orders()