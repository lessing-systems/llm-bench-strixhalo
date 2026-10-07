from .config import TAX_RATES, DEFAULT_REGION


def price_with_tax(amount: float, region: str = DEFAULT_REGION) -> float:
    rate = TAX_RATES[region]
    return round(amount * rate, 2)


def bulk_discount(qty: int) -> float:
    """Return discount fraction: 5% from 10 units, 10% from 50 units, 15% from 100 units."""
    if qty > 100:
        return 0.15
    if qty > 50:
        return 0.10
    if qty > 10:
        return 0.05
    return 0.0
