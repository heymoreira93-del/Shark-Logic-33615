"""
Built-in skip-trace provider (no BatchData required).

Uses RentCast property records for owner name + mailing address.
Phone/email are not in RentCast public records — those stay blank unless
you later plug in a people-data vendor.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

RENTCAST_BASE = "https://api.rentcast.io/v1"


def _rentcast_headers() -> dict[str, str]:
    key = (os.getenv("RENTCAST_API_KEY") or "").strip()
    return {"accept": "application/json", "X-Api-Key": key}


def has_provider() -> bool:
    key = (os.getenv("RENTCAST_API_KEY") or "").strip()
    return bool(key) and key not in {"your_key_here", "your_rentcast_key"}


def _owner_from_prop(prop: dict[str, Any], address: str) -> dict[str, Any]:
    owner = prop.get("owner") or {}
    names = owner.get("names") or []
    if isinstance(names, str):
        names = [names]
    owner_name = ", ".join(n for n in names if n) if names else ""

    mailing = owner.get("mailingAddress") or {}
    if isinstance(mailing, dict):
        mailing_address = (
            mailing.get("formattedAddress")
            or ", ".join(
                str(x)
                for x in (
                    mailing.get("addressLine1"),
                    mailing.get("city"),
                    mailing.get("state"),
                    mailing.get("zipCode"),
                )
                if x
            )
            or address
        )
    else:
        mailing_address = str(mailing or address)

    return {
        "owner_name": owner_name or "Owner on file (name unavailable)",
        "phone": "",  # RentCast does not provide owner cell numbers
        "email": "",
        "mailing_address": mailing_address or address,
        "owner_type": owner.get("type") or "",
        "owner_occupied": prop.get("ownerOccupied"),
        "source": "rentcast",
    }


def rentcast_skip_trace(address: str) -> dict[str, Any] | None:
    """Pull current owner from RentCast /properties."""
    address = (address or "").strip()
    if not address or not has_provider():
        return None

    # Try full address, then a lightly normalized variant
    candidates = [address]
    compact = " ".join(address.replace(",", " ").split())
    if compact not in candidates:
        candidates.append(compact)

    last_exc: Exception | None = None
    for addr in candidates:
        try:
            url = f"{RENTCAST_BASE}/properties?address={quote(addr)}"
            resp = requests.get(url, headers=_rentcast_headers(), timeout=25)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, list):
                if not payload:
                    continue
                prop = payload[0]
            elif isinstance(payload, dict):
                prop = payload
            else:
                continue
            return _owner_from_prop(prop, address)
        except Exception as exc:
            last_exc = exc
            print(f"RentCast skip-trace error: {exc}")
            continue

    if last_exc:
        print(f"RentCast skip-trace exhausted variants: {last_exc}")
    return None
