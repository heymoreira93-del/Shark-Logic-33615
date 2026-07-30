"""
Rehab + Florida / Tampa hazard adjustments.
"""

from __future__ import annotations

from typing import Any

from tampa_config import (
    DEFAULT_CLOSING_COST_PCT,
    ELEVATED_FLOOD_ZIPS,
    FLOOD_BUFFER,
    FLOOD_ZIPS,
    FL_DOC_STAMP_PER_100,
    HIGH_FLOOD_ZIPS,
    HIGH_RISK_FLOOD_HIT,
    MANUAL_FLOOD_MAO_HIT,
    MIN_WHOLESALE_FEE,
    MODERATE_FLOOD_BUFFER,
    MODERATE_FLOOD_ZIPS,
    MOLD_HUMIDITY_BUFFER_33615,
)

# Re-export for `from rehab import DEFAULT_CLOSING_COST_PCT` etc.
__all__ = [
    "DEFAULT_CLOSING_COST_PCT",
    "FLOOD_BUFFER",
    "FLOOD_ZIPS",
    "FL_DOC_STAMP_PER_100",
    "HIGH_FLOOD_ZIPS",
    "HIGH_RISK_FLOOD_HIT",
    "MANUAL_FLOOD_MAO_HIT",
    "MIN_WHOLESALE_FEE",
    "MODERATE_FLOOD_BUFFER",
    "MODERATE_FLOOD_ZIPS",
    "MOLD_HUMIDITY_BUFFER_33615",
    "REPAIR_MENU",
    "apply_tampa_risk_adjustments",
    "calculate_rehab",
    "florida_closing_costs",
    "florida_doc_stamps",
    "line_cost",
    "repair_options",
    "shark_mao",
    "tampa_hazard_check",
]

REPAIR_MENU: dict[str, dict[str, Any]] = {
    "Roof": {"kind": "sqft", "rate": 8.0, "label": "Roof ($8/sqft)"},
    "Paint": {"kind": "sqft", "rate": 3.0, "label": "Paint ($3/sqft)"},
    "Kitchen": {"kind": "flat", "amount": 15000.0, "label": "Kitchen ($15,000)"},
    "HVAC": {"kind": "flat", "amount": 8000.0, "label": "HVAC ($8,000)"},
    "Windows": {"kind": "flat", "amount": 12000.0, "label": "Windows ($12,000 base)"},
}


def repair_options() -> list[str]:
    return list(REPAIR_MENU.keys())


def line_cost(item: str, sqft: float, hvhz: bool = False) -> float:
    spec = REPAIR_MENU[item]
    if spec["kind"] == "sqft":
        cost = float(sqft) * float(spec["rate"])
    else:
        cost = float(spec["amount"])
    if hvhz and item == "Windows":
        cost *= 1.5
    return cost


def calculate_rehab(
    selected: list[str],
    sqft: float,
    *,
    hvhz: bool = False,
) -> dict[str, Any]:
    lines: list[dict[str, Any]] = []
    total = 0.0
    for name in selected:
        if name not in REPAIR_MENU:
            continue
        cost = line_cost(name, sqft, hvhz=hvhz)
        total += cost
        spec = REPAIR_MENU[name]
        if spec["kind"] == "sqft":
            detail = f"${spec['rate']:.0f}/sqft x {sqft:,.0f} sqft"
        elif name == "Windows" and hvhz:
            detail = "flat allowance x 1.5 HVHZ"
        else:
            detail = "flat allowance"
        lines.append({"item": name, "detail": detail, "cost": cost})
    return {"lines": lines, "total": total}


def tampa_hazard_check(zip_code: str) -> dict[str, Any]:
    """Flag Tampa Bay flood zips including elevated 33615 Town 'N' Country."""
    z = (zip_code or "").strip()[:5]

    if z in ELEVATED_FLOOD_ZIPS:
        buffer = float(ELEVATED_FLOOD_ZIPS[z]) + MOLD_HUMIDITY_BUFFER_33615
        return {
            "risk_level": "ELEVATED FLOOD RISK",
            "buffer_deduction": buffer,
            "warning": (
                "33615 Town 'N' Country / Rocky Point — Sweetwater Creek & Old Tampa Bay. "
                "Insurance + humidity/mold cushion applied. Verify premiums before locking MAO."
            ),
            "is_flood_zip": True,
            "tier": "elevated",
        }

    if z in HIGH_FLOOD_ZIPS:
        return {
            "risk_level": "HIGH (Flood Zone)",
            "buffer_deduction": FLOOD_BUFFER,
            "warning": (
                "SOUTH TAMPA / COASTAL / BEACH FLOOD PLAIN DETECTED — "
                "verify flood insurance premiums before finalizing MAO."
            ),
            "is_flood_zip": True,
            "tier": "high",
        }

    if z in MODERATE_FLOOD_ZIPS:
        return {
            "risk_level": "MODERATE (Flood Zone)",
            "buffer_deduction": MODERATE_FLOOD_BUFFER,
            "warning": (
                "RIVERVIEW / APOLLO BEACH flood exposure — "
                "confirm premiums and elevation before locking MAO."
            ),
            "is_flood_zip": True,
            "tier": "moderate",
        }

    return {
        "risk_level": "Standard",
        "buffer_deduction": 0.0,
        "warning": "",
        "is_flood_zip": False,
        "tier": "low",
    }


def apply_tampa_risk_adjustments(zip_code: str, base_mao: float) -> dict[str, Any]:
    details = tampa_hazard_check(zip_code)
    details["adjusted_mao"] = float(base_mao) - float(details["buffer_deduction"])
    return details


def florida_doc_stamps(purchase_price: float) -> float:
    return (float(purchase_price) / 100.0) * FL_DOC_STAMP_PER_100


def florida_closing_costs(purchase_price: float, pct: float = DEFAULT_CLOSING_COST_PCT) -> float:
    return float(purchase_price) * float(pct)


def shark_mao(
    arv: float,
    rehab: float,
    fee: float,
    market_factor: float = 0.70,
    *,
    flood_buffer: float = 0.0,
    closing_cost_pct: float = DEFAULT_CLOSING_COST_PCT,
) -> dict[str, float]:
    fee = max(float(fee), MIN_WHOLESALE_FEE)
    closing = florida_closing_costs(arv, closing_cost_pct)
    mao = (arv * market_factor) - rehab - fee - flood_buffer - closing
    return {
        "Aggressive": mao,
        "Mid": mao * 0.90,
        "Safe": mao * 0.80,
        "fee_used": fee,
        "closing_costs": closing,
        "flood_buffer": flood_buffer,
    }
