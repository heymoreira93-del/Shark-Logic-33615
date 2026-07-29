"""
Skip-trace hunter — locate owner from property address.

v1 uses mock data so the UI works offline. Set SKIP_TRACE_API_URL +
SKIP_TRACE_API_KEY in .env to hit a real provider (BatchData, AbstractAPI, etc.).
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()


def skip_trace(address: str) -> dict[str, Any] | None:
    """
    Return owner contact fields for an address.

    Expected keys: owner_name, phone, email, mailing_address
    """
    address = (address or "").strip()
    if not address:
        return None

    api_url = os.getenv("SKIP_TRACE_API_URL", "").strip()
    api_key = os.getenv("SKIP_TRACE_API_KEY", "").strip()

    if api_url and api_key:
        try:
            url = api_url.format(address=quote(address), api_key=api_key)
            if "{address}" not in api_url:
                # Generic query-param style fallback
                sep = "&" if "?" in api_url else "?"
                url = f"{api_url}{sep}address={quote(address)}&api_key={api_key}"
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()
            return {
                "owner_name": data.get("owner_name") or data.get("name") or "",
                "phone": data.get("phone") or data.get("mobile") or "",
                "email": data.get("email") or "",
                "mailing_address": data.get("mailing_address") or data.get("mailing") or address,
            }
        except Exception as exc:
            print(f"Skip trace API error: {exc}")
            return None

    # Offline mock — swap for a real provider when keys are set
    return {
        "owner_name": "John Doe",
        "phone": "555-0199",
        "email": "johndoe@example.com",
        "mailing_address": address,
    }
