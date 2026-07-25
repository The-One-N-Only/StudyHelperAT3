"""Australian Bureau of Statistics data integration."""

import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ABS_API = "https://api.data.abs.gov.au/data"

# Common ABS datasets
DATASETS = {
    "CPI": {"id": "CPI", "name": "Consumer Price Index", "frequency": "quarterly"},
    "LABOUR_FORCE": {"id": "LF", "name": "Labour Force Survey", "frequency": "monthly"},
    "POPULATION": {"id": "ERP", "name": "Estimated Resident Population", "frequency": "quarterly"},
    "GDP": {"id": "GDP", "name": "Gross Domestic Product", "frequency": "quarterly"},
    "WAGES": {"id": "WPI", "name": "Wage Price Index", "frequency": "quarterly"},
}

def search_datasets(query: str) -> list[dict]:
    """Search available ABS datasets."""
    query_lower = query.lower()
    results = []
    for code, info in DATASETS.items():
        if query_lower in info["name"].lower() or query_lower in code.lower():
            results.append({
                "dataset_code": code,
                "name": info["name"],
                "frequency": info["frequency"],
                "source": "ABS",
            })
    return results

def get_dataset_data(dataset_code: str) -> Optional[dict]:
    """Fetch latest data for a dataset."""
    dataset = DATASETS.get(dataset_code)
    if not dataset:
        return None

    try:
        resp = requests.get(
            f"{ABS_API}/{dataset['id']}/latest",
            params={"format": "jsondata"},
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            return {
                "name": dataset["name"],
                "source": "ABS",
                "frequency": dataset["frequency"],
                "data": data,
                "url": f"https://www.abs.gov.au/statistics/{dataset['id'].lower()}",
            }
    except Exception as e:
        logger.error(f"ABS API error: {e}")

    return {
        "name": dataset["name"],
        "source": "ABS",
        "frequency": dataset["frequency"],
        "url": f"https://www.abs.gov.au/statistics/{dataset['id'].lower()}",
        "note": "Live data unavailable. Visit ABS website for latest figures.",
    }
