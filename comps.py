"""
Comps engine — prefers RentCast live solds; mock fallback via data_engine.
"""

from __future__ import annotations

from typing import Any

from data_engine import get_tampa_comps, get_tampa_data


def search_comps(arv: float, address: str = "") -> list[dict[str, Any]]:
    """
    Live Tampa comps when RENTCAST_API_KEY is set; otherwise mock solds.
    `arv` kept for API compatibility with older callers.
    """
    _ = arv
    return get_tampa_comps(address or "Tampa, FL")


def get_property_data(address: str) -> dict[str, Any] | None:
    from data_engine import get_property_data as _gpd

    return _gpd(address)


def live_arv_bundle(address: str) -> dict[str, Any]:
    """Convenience wrapper used by the UI Pull Live Data button."""
    return get_tampa_data(address)
