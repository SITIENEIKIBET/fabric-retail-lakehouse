"""
Generates a synthetic CSV representing a "legacy loyalty program export" —
simulating a batch file drop from an older system with realistic legacy-style
data quality issues (inconsistent dates, encoding quirks, manual-entry errors).

Usage:
    python scripts/generate_loyalty_csv.py
"""
import csv
import logging
import os
import random
from datetime import datetime, timedelta

from faker import Faker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

fake = Faker()
Faker.seed(7)
random.seed(7)

OUTPUT_DIR = "data/raw/loyalty"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "loyalty_export.csv")
N_RECORDS = 300

# Legacy systems often used inconsistent date formats across different eras
DATE_FORMATS = ["%m/%d/%Y", "%d-%m-%Y", "%Y.%m.%d"]

TIERS = ["Bronze", "Silver", "Gold", "Platinum"]


def random_legacy_date(start_days_ago=1500, end_days_ago=1):
    """Simulate a legacy system's inconsistent date formatting across records."""
    d = datetime.now() - timedelta(days=random.randint(end_days_ago, start_days_ago))
    fmt = random.choice(DATE_FORMATS)
    return d.strftime(fmt)


def generate_records(n=N_RECORDS):
    records = []
    for i in range(n):
        member_id = f"LOY-{1000 + i}"
        full_name = fake.name()

        # ~4% of names have manual-entry casing issues (all caps, common in legacy systems)
        if random.random() < 0.04:
            full_name = full_name.upper()

        email = fake.email()
        # ~6% missing email entirely (legacy systems often didn't require it)
        if random.random() < 0.06:
            email = ""

        points_balance = random.randint(0, 15000)
        tier = random.choice(TIERS)

        # ~3% of records have a negative points balance due to a known legacy bug
        # (simulates a real upstream data quality issue you'd have to catch in Silver)
        if random.random() < 0.03:
            points_balance = -abs(points_balance)

        enrollment_date = random_legacy_date()

        records.append({
            "member_id": member_id,
            "full_name": full_name,
            "email": email,
            "points_balance": points_balance,
            "tier": tier,
            "enrollment_date": enrollment_date,
        })

    # Inject a handful of exact duplicate rows (simulates a re-run export bug)
    dup_sample = random.sample(records, k=5)
    records.extend(dup_sample)

    return records


def write_csv(records):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fieldnames = ["member_id", "full_name", "email", "points_balance", "tier", "enrollment_date"]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    logger.info("Wrote %d records (including 5 duplicates) to %s", len(records), OUTPUT_FILE)


def main():
    records = generate_records()
    write_csv(records)


if __name__ == "__main__":
    main()