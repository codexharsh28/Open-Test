"""Small demonstration module for Open Test's generated-test workflow.

Discount tiers are intentionally explicit so generated tests can assert stable
behavior: standard (0%), silver (10%), and gold (20%).
"""

from __future__ import annotations

import math


_DISCOUNT_RATES = {
    "standard": 0.0,
    "silver": 0.10,
    "gold": 0.20,
}


def calculate_discount(price: float, tier: str) -> float:
    """Return the final price after applying a tier discount.

    Prices must be finite and non-negative. Tier names are case-insensitive,
    and the returned amount is rounded to two decimal places using Python's
    standard ``round`` behavior.
    """
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        raise TypeError("price must be a number")
    try:
        finite_price = math.isfinite(price)
    except OverflowError:
        finite_price = False
    if not finite_price:
        raise ValueError("price must be finite")
    if price < 0:
        raise ValueError("price cannot be negative")
    if not isinstance(tier, str):
        raise TypeError("tier must be a string")

    normalized_tier = tier.strip().lower()
    try:
        rate = _DISCOUNT_RATES[normalized_tier]
    except KeyError as exc:
        raise ValueError(f"unknown tier: {tier!r}") from exc

    return round(price * (1 - rate), 2)


def clean_username(name: str) -> str:
    """Trim a username and remove non-alphanumeric characters.

    ``None`` is treated as an empty username. Alphanumeric Unicode characters
    are retained; whitespace and punctuation/symbols are removed.
    """
    if name is None:
        return ""
    if not isinstance(name, str):
        raise TypeError("name must be a string or None")

    return "".join(character for character in name.strip() if character.isalnum())
