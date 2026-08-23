"""
Skip-trace hunter — locate owner from property address.

Provider order:
1. Built-in RentCast (owner name + mailing) — uses RENTCAST_API_KEY
2. External SKIP_TRACE_API_URL + SKIP_TRACE_API_KEY
3. Empty + error if nothing is configured (no invented owner)
Then optional PEOPLE_DATA / BatchData enrichment for cell + email.
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
                "owner_name": "",
                "phone": "",
                "email": "",
                "mailing_address": address,
                "source": "not_configured",
                "error": (
                    "Skip-trace is OFF — set RENTCAST_API_KEY (owner name) "
                    "and/or SKIP_TRACE_API_URL + SKIP_TRACE_API_KEY. "
                    "Paste owner/phone manually until then."
                ),
            }

    needs_phone = not (hit.get("phone") or "").strip()
    needs_email = not (hit.get("email") or "").strip()
    if needs_phone or needs_email:
        enrich = enrich_phone(
            owner_name=str(hit.get("owner_name") or ""),
            address=address,
            mailing_address=str(hit.get("mailing_address") or ""),
        )
        src = enrich.get("source") or "people_data"
        if enrich.get("phone") and needs_phone:
            hit["phone"] = enrich["phone"]
            hit["phone_source"] = src
        if enrich.get("email") and needs_email:
            hit["email"] = enrich["email"]
            hit["email_source"] = src
        # Prefer BatchData name only when RentCast left a placeholder
        ename = (enrich.get("owner_name") or "").strip()
        oname = (hit.get("owner_name") or "").strip().lower()
        if ename and (not oname or oname.startswith("owner on file")):
            hit["owner_name"] = ename

        if needs_phone and not (hit.get("phone") or "").strip():
            hit["phone_error"] = enrich.get("error") or (
                "No cell found. Add BATCHDATA_API_KEY or paste mobile manually."
                if not people_data_configured()
                else "Phone vendor returned no number for this address."
            )
        if needs_email and not (hit.get("email") or "").strip():
            if people_data_configured():
                hit["email_error"] = (
                    enrich.get("error")
                    or "Vendor returned no email for this address."
                )
            else:
                hit["email_error"] = (
                    "No email vendor configured. Add BATCHDATA_API_KEY "
                    "or paste email manually."
                )

    return hit
