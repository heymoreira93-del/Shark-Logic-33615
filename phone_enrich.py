"""
Phone enrichment — cell numbers are NOT in RentCast.

Order:
1. PEOPLE_DATA_API_URL + PEOPLE_DATA_API_KEY (BatchData / Tracerfy / any HTTP)
2. Manual fallback (returns empty — UI asks you to paste)

Expected people-data JSON fields (flexible):
  phone / mobile / phones[0] / phone_number
"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()


def _ensure_secrets() -> None:
    try:
        from secrets_bootstrap import bootstrap_secrets

        bootstrap_secrets()
    except Exception:
        pass


def people_data_configured() -> bool:
    _ensure_secrets()
    url = (os.getenv("PEOPLE_DATA_API_URL") or "").strip()
    key = (os.getenv("PEOPLE_DATA_API_KEY") or "").strip()
    if not url or not key:
        return False
    # Empty-string placeholders from secrets.toml.example
    if key in {"paste_vendor_key", "your_key_here"}:
        return False
    return True


def _first_phone(data: dict[str, Any]) -> str:
    for key in ("phone", "mobile", "phone_number", "cell", "Phone"):
        val = data.get(key)
        if val:
            return _digits_e164(str(val))
    phones = data.get("phones") or data.get("phoneNumbers") or []
    if isinstance(phones, list) and phones:
        first = phones[0]
        if isinstance(first, dict):
            return _digits_e164(str(first.get("number") or first.get("phone") or ""))
        return _digits_e164(str(first))
    return ""


def _digits_e164(raw: str) -> str:
    p = re.sub(r"[^\d+]", "", (raw or "").strip())
    if p.startswith("++"):
        p = "+" + p[2:]
    digits = re.sub(r"\D", "", p)
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    if p.startswith("+") and len(digits) >= 10:
        return "+" + digits
    return p


def enrich_phone(
    *,
    owner_name: str = "",
    address: str = "",
    mailing_address: str = "",
) -> dict[str, Any]:
    """
    Try people-data vendor for a cell. Returns {phone, source, error}.
    """
    _ensure_secrets()
    if not people_data_configured():
        return {
            "phone": "",
            "source": "none",
            "error": (
                "No PEOPLE_DATA_API_URL / PEOPLE_DATA_API_KEY. "
                "Paste mobile manually or add a people-data vendor."
            ),
        }

    api_url = (os.getenv("PEOPLE_DATA_API_URL") or "").strip()
    api_key = (os.getenv("PEOPLE_DATA_API_KEY") or "").strip()
    name_q = quote(owner_name or "")
    addr_q = quote(mailing_address or address or "")

    try:
        if "{name}" in api_url or "{address}" in api_url:
            url = api_url.format(
                name=name_q,
                address=addr_q,
                api_key=api_key,
            )
        else:
            sep = "&" if "?" in api_url else "?"
            url = (
                f"{api_url}{sep}name={name_q}&address={addr_q}&api_key={quote(api_key)}"
            )
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Api-Key": api_key,
                "accept": "application/json",
            },
            timeout=25,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return {"phone": "", "source": "people_data", "error": "Unexpected response"}
        phone = _first_phone(data)
        return {
            "phone": phone,
            "source": "people_data",
            "error": "" if phone else "Vendor returned no phone",
        }
    except Exception as exc:
        return {"phone": "", "source": "people_data", "error": str(exc)}
