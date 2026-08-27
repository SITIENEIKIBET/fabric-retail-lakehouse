"""
Appends synthetic order_items for the late-arriving orders (order_ids
2001-2003, customer_ids 9001-9003) injected by
inject_late_arriving_orders.py.

Without matching order_items, the late-arriving orders would have no line
items and therefore wouldn't produce any rows in fact_orders (which is
built at the order-item grain) — this script ensures the late-arriving
scenario actually flows all the way through to the fact table.

Usage:
    python scripts/inject_late_arriving_order_items.py
"""
import csv
import logging
import random
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ORDER_ITEMS_CSV = "data/raw/postgres/order_items.csv"
LATE_ORDER_IDS = [2001, 2002, 2003]

random.seed(2003)


def get_next_order_item_id() -> int:
    with open(ORDER_ITEMS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        max_id = max(int(row["order_item_id"]) for row in reader)
    return max_id + 1


def append_late_order_items():
    next_id = get_next_order_item_id()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(ORDER_ITEMS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for i, order_id in enumerate(LATE_ORDER_IDS):
            order_item_id = next_id + i
            product_id = random.randint(1, 100)  # valid product range, avoids Silver quarantine
            quantity = random.randint(1, 3)
            unit_price = round(random.uniform(5, 500), 2)
            writer.writerow([order_item_id, order_id, product_id, quantity, unit_price, now])

    logger.info(
        "Appended %d order_items (order_item_ids %d-%d) across orders %s.",
        len(LATE_ORDER_IDS), next_id, next_id + len(LATE_ORDER_IDS) - 1, LATE_ORDER_IDS,
    )


if __name__ == "__main__":
    append_late_order_items()