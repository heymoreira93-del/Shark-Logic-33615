"""
Phone enrichment — cell numbers are NOT in RentCast.

Order:
1. BatchData Property Skip Trace (BATCHDATA_API_KEY or PEOPLE_DATA_API_KEY alone)
2. Generic PEOPLE_DATA_API_URL + PEOPLE_DATA_API_KEY (GET with {name}/{address})
3. Manual fallback (empty — UI asks you to paste)

Expected generic JSON fields (flexible):
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

BATCHDATA_SKIP_TRACE_URL = "https://api.batchdata.com/api/v1/property/skip-trace"


def _ensure_secrets() -> None:
    try:
        from secrets_bootstrap import bootstrap_secrets

        bootstrap_secrets()
    except Exception:
        pass


def _is_placeholder(val: str | None) -> bool:
    try:
        from secrets_bootstrap import is_placeholder_secret

        return is_placeholder_secret(val)
    except Exception:
        return not (val or "").strip()


def _people_env(name: str) -> str:
    """Resolve people-data URL/key including SKIP_TRACE_* / BATCHDATA_* aliases."""
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
        "BATCHDATA_API_KEY": (
            "BATCHDATA_API_KEY",
            "PEOPLE_DATA_API_KEY",
            "SKIP_TRACE_API_KEY",
        ),
    }
    for alt in aliases.get(name, (name,)):
        val = (os.getenv(alt) or "").strip()
        if val and not _is_placeholder(val):
            if alt != name:
                os.environ[name] = val
            return val
    return ""


def batchdata_configured() -> bool:
    return bool(_people_env("BATCHDATA_API_KEY"))


def people_data_configured() -> bool:
    """True when BatchData key OR generic URL+key pair is present."""
    if batchdata_configured():
        return True
    url = _people_env("PEOPLE_DATA_API_URL")
    key = _people_env("PEOPLE_DATA_API_KEY")
    # URL that is literally the BatchData endpoint still needs only the key
    if key and (not url or "batchdata.com" in url.lower()):
        return True
    return bool(url and key)


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


def _first_phone(data: dict[str, Any]) -> str:
    for key in ("phone", "mobile", "phone_number", "cell", "Phone"):
        val = data.get(key)
        if val:
            return _digits_e164(str(val))
    phones = data.get("phones") or data.get("phoneNumbers") or []
    if isinstance(phones, list) and phones:
        # Prefer mobile / wireless when typed
        ranked: list[Any] = []
        other: list[Any] = []
        for item in phones:
            if isinstance(item, dict):
                typ = str(item.get("type") or item.get("phoneType") or "").lower()
                if "mobile" in typ or "cell" in typ or "wireless" in typ:
                    ranked.append(item)
                else:
                    other.append(item)
            else:
                other.append(item)
        for first in ranked + other:
            if isinstance(first, dict):
                num = _digits_e164(
                    str(first.get("number") or first.get("phone") or first.get("value") or "")
                )
            else:
                num = _digits_e164(str(first))
            if num:
                return num
    return ""


def _parse_us_address(address: str) -> dict[str, str]:
    """Split '1911 E 115th Ave, Tampa, FL 33612' into BatchData propertyAddress fields."""
    raw = (address or "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    street = parts[0] if parts else raw
    city = parts[1] if len(parts) > 1 else ""
    state = ""
    zip_code = ""
    tail = " ".join(parts[2:]) if len(parts) > 2 else (parts[1] if len(parts) == 2 else "")
    m = re.search(r"\b([A-Za-z]{2})\s+(\d{5})(?:-\d{4})?\b", tail or raw)
    if m:
        state = m.group(1).upper()
        zip_code = m.group(2)
        if not city and len(parts) >= 2:
            # "Tampa FL 33612" style single tail after street
            city_candidate = re.sub(
                r"\b[A-Za-z]{2}\s+\d{5}(?:-\d{4})?\b", "", parts[1]
            ).strip(" ,")
            if city_candidate:
                city = city_candidate
    elif len(parts) >= 2:
        m2 = re.search(r"\b([A-Za-z]{2})\b", parts[-1])
        m3 = re.search(r"\b(\d{5})(?:-\d{4})?\b", parts[-1])
        if m2:
            state = m2.group(1).upper()
        if m3:
            zip_code = m3.group(1)
    return {
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
    }


def _phones_from_batchdata(payload: Any) -> tuple[str, str, str]:
    """
    Walk BatchData skip-trace JSON. Returns (phone, email, owner_name).
    """
    phone = ""
    email = ""
    owner = ""

    results = []
    if isinstance(payload, dict):
        results = payload.get("results") or payload.get("persons") or []
        if not results and payload.get("result"):
            results = [payload["result"]]
    elif isinstance(payload, list):
        results = payload

    for result in results:
        if not isinstance(result, dict):
            continue
        persons = result.get("persons") or result.get("owners") or []
        if not persons and (result.get("phoneNumbers") or result.get("phones")):
            persons = [result]
        if isinstance(persons, dict):
            persons = [persons]
        for person in persons:
            if not isinstance(person, dict):
                continue
            if not owner:
                name = person.get("name") or {}
                if isinstance(name, dict):
                    owner = str(name.get("full") or name.get("fullName") or "").strip()
                else:
                    owner = str(
                        person.get("fullName") or person.get("owner_name") or name or ""
                    ).strip()
            if not phone:
                phone = _first_phone(person)
            if not email:
                emails = person.get("emails") or person.get("emailAddresses") or []
                if isinstance(emails, list) and emails:
                    first = emails[0]
                    if isinstance(first, dict):
                        email = str(first.get("email") or first.get("address") or "").strip()
                    else:
                        email = str(first).strip()
                elif person.get("email"):
                    email = str(person.get("email")).strip()
            if phone:
                return phone, email, owner
        if not phone:
            phone = _first_phone(result)
            if phone:
                return phone, email, owner
    return phone, email, owner


def _enrich_batchdata(
    *,
    owner_name: str,
    address: str,
    mailing_address: str,
) -> dict[str, Any]:
    api_key = _people_env("BATCHDATA_API_KEY")
    if not api_key:
        return {
            "phone": "",
            "source": "none",
            "error": "Missing BATCHDATA_API_KEY",
        }

    prop_addr = _parse_us_address(mailing_address or address)
    if not prop_addr.get("street"):
        return {
            "phone": "",
            "source": "batchdata",
            "error": "Address required for BatchData skip-trace",
        }

    body: dict[str, Any] = {
        "requests": [{"propertyAddress": {k: v for k, v in prop_addr.items() if v}}],
        "options": {"includeTCPABlacklistedPhones": False},
    }
    # Optional name hint when RentCast already found the owner
    if owner_name and owner_name.lower() not in {"owner on file (name unavailable)"}:
        # BatchData accepts person name on some versions; keep property-first.
        body["requests"][0]["ownerName"] = owner_name

    try:
        resp = requests.post(
            BATCHDATA_SKIP_TRACE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=35,
        )
        if resp.status_code == 401:
            return {
                "phone": "",
                "email": "",
                "source": "batchdata",
                "error": "BatchData 401 — check BATCHDATA_API_KEY",
            }
        if resp.status_code in (402, 403):
            detail = ""
            try:
                detail = str((resp.json().get("status") or {}).get("message") or "")
            except Exception:
                detail = (resp.text or "")[:120]
            low = detail.lower()
            if "balance" in low or "insufficient" in low or resp.status_code == 402:
                return {
                    "phone": "",
                    "email": "",
                    "source": "batchdata",
                    "error": (
                        "BatchData wallet empty (insufficient balance). "
                        "Top up credits at https://app.batchdata.io then Skip Trace again."
                    ),
                }
            return {
                "phone": "",
                "email": "",
                "source": "batchdata",
                "error": f"BatchData {resp.status_code}: {detail or 'Forbidden'}",
            }
        resp.raise_for_status()
        phone, email, name = _phones_from_batchdata(resp.json())
        missing = []
        if not phone:
            missing.append("phone")
        if not email:
            missing.append("email")
        out: dict[str, Any] = {
            "phone": phone,
            "email": email,
            "source": "batchdata",
            "error": (
                ""
                if not missing
                else f"BatchData returned no {'/'.join(missing)} for this address"
            ),
        }
        if name:
            out["owner_name"] = name
        return out
    except Exception as exc:
        return {"phone": "", "source": "batchdata", "error": str(exc)}


def _enrich_generic_http(
    *,
    owner_name: str,
    address: str,
    mailing_address: str,
) -> dict[str, Any]:
    api_url = _people_env("PEOPLE_DATA_API_URL")
    api_key = _people_env("PEOPLE_DATA_API_KEY")
    if not api_url or not api_key:
        return {
            "phone": "",
            "source": "none",
            "error": (
                "No phone vendor configured. Add BATCHDATA_API_KEY "
                "(or PEOPLE_DATA_API_URL + PEOPLE_DATA_API_KEY), then Skip Trace again."
            ),
        }

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
            return {
                "phone": "",
                "email": "",
                "source": "people_data",
                "error": "Unexpected response",
            }
        phone = _first_phone(data)
        email = ""
        bd_phone, bd_email, bd_name = _phones_from_batchdata(data)
        phone = phone or bd_phone
        email = str(data.get("email") or data.get("Email") or bd_email or "").strip()
        missing = []
        if not phone:
            missing.append("phone")
        if not email:
            missing.append("email")
        out: dict[str, Any] = {
            "phone": phone,
            "email": email,
            "source": "people_data",
            "error": (
                ""
                if not missing
                else f"Vendor returned no {'/'.join(missing)}"
            ),
        }
        if bd_name:
            out["owner_name"] = bd_name
        return out
    except Exception as exc:
        return {"phone": "", "email": "", "source": "people_data", "error": str(exc)}


def enrich_phone(
    *,
    owner_name: str = "",
    address: str = "",
    mailing_address: str = "",
) -> dict[str, Any]:
    """
    Try people-data vendor for cell + email.
    Returns {phone, email, source, error, owner_name?}.
    """
    _ensure_secrets()
    if not people_data_configured():
        return {
            "phone": "",
            "email": "",
            "source": "none",
            "error": (
                "No contact vendor configured. Add BATCHDATA_API_KEY in `.env` "
                "(https://batchdata.io -> API Keys), or PEOPLE_DATA_API_URL + KEY. "
                "RentCast does not return cell phones or emails."
            ),
        }

    # Prefer native BatchData POST when key is present (URL optional).
    url = _people_env("PEOPLE_DATA_API_URL")
    if batchdata_configured() or (not url) or ("batchdata.com" in url.lower()):
        hit = _enrich_batchdata(
            owner_name=owner_name,
            address=address,
            mailing_address=mailing_address,
        )
        if hit.get("phone") or hit.get("email") or hit.get("source") == "batchdata":
            return hit

    return _enrich_generic_http(
        owner_name=owner_name,
        address=address,
        mailing_address=mailing_address,
    )
