"""
Generates a synthetic JSON file representing a product reviews feed —
simulating a nested, document-shaped source (e.g. from a reviews microservice
or NoSQL-backed system) distinct from the flat CSV and relational Postgres sources.

Usage:
    python scripts/generate_reviews_json.py
"""
import json
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
Faker.seed(21)
random.seed(21)

OUTPUT_DIR = "data/raw/reviews"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "product_reviews.json")
N_REVIEWS = 400
N_PRODUCTS = 100  # should align loosely with the 100 products seeded in Postgres

REVIEW_PHRASES = [
    "Great value for the price.",
    "Not what I expected, quality was disappointing.",
    "Fast shipping and well packaged.",
    "Exactly as described, very happy.",
    "Broke after a week of use.",
    "Would definitely buy again.",
    "Customer service was unhelpful when I had an issue.",
    "Perfect gift, highly recommend.",
]


def generate_review(review_id: int) -> dict:
    product_id = random.randint(1, N_PRODUCTS)

    # ~2% of reviews reference a product_id outside the valid range
    # (simulates schema drift / stale product references from the reviews service)
    if random.random() < 0.02:
        product_id = N_PRODUCTS + random.randint(50, 200)

    review_date = datetime.now() - timedelta(days=random.randint(1, 730))

    review = {
        "review_id": f"REV-{review_id:05d}",
        "product_id": product_id,
        "reviewer": {
            "name": fake.name(),
            # nested structure — reviewer is a sub-object, not a flat field
            "verified_purchase": random.random() > 0.15,
            "location": {
                "city": fake.city(),
                "country": fake.country(),
            },
        },
        "rating": random.randint(1, 5),
        "review_text": random.choice(REVIEW_PHRASES),
        "review_date": review_date.strftime("%Y-%m-%dT%H:%M:%S"),
        "helpful_votes": random.randint(0, 250),
        # tags is an array field — another common nested-data shape to handle
        "tags": random.sample(
            ["quality", "value", "shipping", "packaging", "durability", "customer_service"],
            k=random.randint(0, 3),
        ),
    }

    # ~5% of reviews are missing a rating entirely (nullable nested field)
    if random.random() < 0.05:
        review["rating"] = None

    return review


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    reviews = [generate_review(i) for i in range(1, N_REVIEWS + 1)]

    payload = {
        "source": "reviews_service_mock",
        "generated_at_utc": datetime.utcnow().isoformat(),
        "review_count": len(reviews),
        "reviews": reviews,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    logger.info("Wrote %d reviews to %s", len(reviews), OUTPUT_FILE)


if __name__ == "__main__":
    main()