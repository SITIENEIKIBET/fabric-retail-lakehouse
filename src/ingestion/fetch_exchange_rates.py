"""
Fetches daily currency exchange rates from the Frankfurter API (ECB reference rates)
and saves them as raw JSON — this represents the REST API source for the retail platform,
used to value international orders in a consistent base currency.

API: https://www.frankfurter.dev (no key required)

Usage:
    python src/ingestion/fetch_exchange_rates.py
"""
import json
import logging
import os
import sys
import time
from datetime import date, datetime

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

API_URL = "https://api.frankfurter.dev/v1/latest"
BASE_CURRENCY = "USD"
OUTPUT_DIR = "data/raw/exchange_rates"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


def fetch_rates(base: str = BASE_CURRENCY) -> dict:
    """Fetch latest exchange rates with retry logic for transient failures."""
    params = {"base": base}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Fetching exchange rates (attempt %d/%d)...", attempt, MAX_RETRIES)
            response = requests.get(API_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning("Request timed out on attempt %d.", attempt)
        except requests.exceptions.HTTPError as e:
            logger.error("HTTP error from API: %s", e)
            if response.status_code < 500:
                # Client-side error (bad request, etc.) — retrying won't help
                raise
        except requests.exceptions.RequestException as e:
            logger.warning("Request failed on attempt %d: %s", attempt, e)

        if attempt < MAX_RETRIES:
            sleep_time = RETRY_BACKOFF_SECONDS * attempt
            logger.info("Retrying in %d seconds...", sleep_time)
            time.sleep(sleep_time)

    logger.error("All %d attempts failed. Giving up.", MAX_RETRIES)
    sys.exit(1)


def save_raw(payload: dict) -> str:
    """Save the raw API response as-is, with an ingestion timestamp for audit purposes."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ingestion_record = {
        "source": "frankfurter_api",
        "ingested_at_utc": datetime.utcnow().isoformat(),
        "raw_response": payload,
    }

    filename = f"{OUTPUT_DIR}/exchange_rates_{date.today().isoformat()}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(ingestion_record, f, indent=2)

    logger.info("Saved exchange rates to %s", filename)
    return filename


def main():
    payload = fetch_rates()
    save_raw(payload)
    logger.info("Exchange rate ingestion completed successfully.")


if __name__ == "__main__":
    main()