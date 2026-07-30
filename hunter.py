"""
Skip-trace hunter — locate owner from property address.

Provider order:
1. Built-in RentCast (owner name + mailing) — uses RENTCAST_API_KEY
2. External SKIP_TRACE_API_URL + SKIP_TRACE_API_KEY
3. Offline mock
Then optional PEOPLE_DATA_API_* cell enrichment (RocketReach / Lusha / PropertyRadar style).
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from phone_enrich import enrich_phone, people_data_configured
from skip_provider import has_provider, rentcast_skip_trace

load_dotenv()


def skip_trace(address: str) -> dict[str, Any] | None:
    """
    Return owner contact fields for an address.

    Expected keys: owner_name, phone, email, mailing_address
    """
    address = (address or "").strip()
    if not address:
        return None

    hit: dict[str, Any] | None = None

    if has_provider():
        hit = rentcast_skip_trace(address)

    api_url = os.getenv("SKIP_TRACE_API_URL", "").strip()
    api_key = os.getenv("SKIP_TRACE_API_KEY", "").strip()

    if not hit and api_url and api_key:
        try:
            if "{address}" in api_url:
                url = api_url.format(address=quote(address), api_key=api_key)
            else:
                sep = "&" if "?" in api_url else "?"
                url = f"{api_url}{sep}address={quote(address)}&api_key={api_key}"
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {api_key}", "X-Api-Key": api_key},
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            hit = {
                "owner_name": data.get("owner_name") or data.get("name") or "",
                "phone": data.get("phone") or data.get("mobile") or "",
                "email": data.get("email") or "",
                "mailing_address": data.get("mailing_address") or data.get("mailing") or address,
                "source": "external",
            }
        except Exception as exc:
            print(f"Skip trace API error: {exc}")

    if not hit:
        # Only invent a demo owner when NOTHING is configured.
        # If RentCast / skip-trace keys exist, surface a miss — never fake an owner.
        if has_provider() or (api_url and api_key):
            hit = {
                "owner_name": "",
                "phone": "",
                "email": "",
                "mailing_address": address,
                "source": "not_found",
                "error": (
                    "Live skip-trace configured but no owner returned for this address. "
                    "Check spelling (include city/state/zip) or paste owner manually."
                ),
            }
        else:
            hit = {
                "owner_name": "John Doe (mock - add RENTCAST_API_KEY for live owner)",
                "phone": "",
                "email": "johndoe@example.com",
                "mailing_address": address,
                "source": "mock",
            }

    if not (hit.get("phone") or "").strip() and people_data_configured():
        enrich = enrich_phone(
            owner_name=str(hit.get("owner_name") or ""),
            address=address,
            mailing_address=str(hit.get("mailing_address") or ""),
        )
        if enrich.get("phone"):
            hit["phone"] = enrich["phone"]
            hit["phone_source"] = enrich.get("source") or "people_data"
        else:
            hit["phone_error"] = enrich.get("error") or ""

    return hit
