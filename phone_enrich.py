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


def _people_env(name: str) -> str:
    """Resolve people-data URL/key including SKIP_TRACE_* aliases."""
    _ensure_secrets()
    aliases = {
        "PEOPLE_DATA_API_URL": (
            "PEOPLE_DATA_API_URL",
            "SKIP_TRACE_API_URL",
            "BATCHDATA_API_URL",
        ),
        "PEOPLE_DATA_API_KEY": (
            "PEOPLE_DATA_API_KEY",
            "SKIP_TRACE_API_KEY",
            "BATCHDATA_API_KEY",
        ),
    }
    try:
        from secrets_bootstrap import is_placeholder_secret
    except Exception:
        def is_placeholder_secret(val: str | None) -> bool:  # type: ignore[misc]
            return not (val or "").strip()

    for alt in aliases.get(name, (name,)):
        val = (os.getenv(alt) or "").strip()
        if val and not is_placeholder_secret(val):
            if alt != name:
                os.environ[name] = val
            return val
    return ""


def people_data_configured() -> bool:
    url = _people_env("PEOPLE_DATA_API_URL")
    key = _people_env("PEOPLE_DATA_API_KEY")
    return bool(url and key)


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

    api_url = _people_env("PEOPLE_DATA_API_URL")
    api_key = _people_env("PEOPLE_DATA_API_KEY")
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
