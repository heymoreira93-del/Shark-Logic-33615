"""
Deal Analyzer — Maximum Allowable Offer (MAO) engine.

Formula: (ARV * Market_Factor) - (Sqft * Rehab_Rate) - Wholesale_Fee = MAO
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class RehabLevel(str, Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


REHAB_RATES: Dict[RehabLevel, float] = {
    RehabLevel.LIGHT: 25.0,
    RehabLevel.MEDIUM: 50.0,
    RehabLevel.HEAVY: 75.0,
}

DEFAULT_MARKET_FACTOR = 0.70


@dataclass(frozen=True)
class DealInputs:
    arv: float
    sqft: float
    fee: float
    rehab_level: RehabLevel = RehabLevel.MEDIUM
    market_factor: float = DEFAULT_MARKET_FACTOR
    rehab_override: float | None = None


@dataclass(frozen=True)
class DealResult:
    arv: float
    sqft: float
    fee: float
    market_factor: float
    rehab_level: RehabLevel
    rehab_rate: float
    rehab_cost: float
    mao: float
    offers: Dict[str, float]

    def summary_lines(self) -> list[str]:
        return [
            f"ARV:              ${self.arv:,.2f}",
            f"Sqft:             {self.sqft:,.0f}",
            f"Market Factor:    {self.market_factor:.0%}",
            f"Rehab Level:      {self.rehab_level.value.title()} (${self.rehab_rate:.0f}/sqft)",
            f"Rehab Cost:       ${self.rehab_cost:,.2f}",
            f"Wholesale Fee:    ${self.fee:,.2f}",
            f"MAO (Aggressive): ${self.mao:,.2f}",
            f"Mid-Range:        ${self.offers['Mid']:,.2f}",
            f"Safe Entry:       ${self.offers['Safe']:,.2f}",
        ]


def rehab_cost(sqft: float, level: RehabLevel, override: float | None = None) -> tuple[float, float]:
    if override is not None:
        rate = override / sqft if sqft else 0.0
        return rate, float(override)
    rate = REHAB_RATES[level]
    return rate, sqft * rate


def calculate_mao(
    arv: float,
    rehab: float,
    fee: float,
    market_factor: float = DEFAULT_MARKET_FACTOR,
) -> Dict[str, float]:
    """Return Aggressive / Mid / Safe offer tiers from the 70% rule."""
    mao = (arv * market_factor) - rehab - fee
    return {
        "Aggressive": mao,
        "Mid": mao * 0.90,
        "Safe": mao * 0.80,
    }


def analyze_deal(inputs: DealInputs) -> DealResult:
    rate, rehab = rehab_cost(inputs.sqft, inputs.rehab_level, inputs.rehab_override)
    offers = calculate_mao(inputs.arv, rehab, inputs.fee, inputs.market_factor)
    return DealResult(
        arv=inputs.arv,
        sqft=inputs.sqft,
        fee=inputs.fee,
        market_factor=inputs.market_factor,
        rehab_level=inputs.rehab_level,
        rehab_rate=rate,
        rehab_cost=rehab,
        mao=offers["Aggressive"],
        offers=offers,
    )


def format_comparison_table(result: DealResult) -> str:
    rows = [
        ("Aggressive (MAO)", result.offers["Aggressive"]),
        ("Mid-Range", result.offers["Mid"]),
        ("Safe Entry", result.offers["Safe"]),
    ]
    header = f"{'Offer Tier':<20} {'Amount':>14}"
    sep = "-" * len(header)
    lines = [header, sep]
    for name, amount in rows:
        lines.append(f"{name:<20} ${amount:>13,.2f}")
    return "\n".join(lines)


def parse_rehab_level(value: str) -> RehabLevel:
    key = value.strip().lower()
    try:
        return RehabLevel(key)
    except ValueError as exc:
        valid = ", ".join(r.value for r in RehabLevel)
        raise ValueError(f"Invalid rehab level '{value}'. Use: {valid}") from exc
