"""Reserve Bank of Australia data integration."""

def get_cash_rate() -> dict:
    """Get current RBA cash rate."""
    return {
        "title": "RBA Cash Rate Target",
        "value": "4.35% (as of Nov 2024)",
        "source": "Reserve Bank of Australia",
        "url": "https://www.rba.gov.au/statistics/cash-rate/",
        "note": "Check RBA website for latest rate decisions.",
    }

def get_exchange_rate(currency: str = "USD") -> dict:
    """Get AUD exchange rate."""
    return {
        "title": f"AUD/{currency} Exchange Rate",
        "source": "Reserve Bank of Australia",
        "url": "https://www.rba.gov.au/statistics/frequency/exchange-rates.html",
        "note": "Visit RBA website for current exchange rates.",
    }
