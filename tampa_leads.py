"""
Scraper Prep — Hillsborough County Clerk public filings (Foreclosures / Lis Pendens).

v1 is a safe placeholder: accepts a filings URL and outlines parse targets.
Do not hammer county sites; respect robots.txt and terms of use.
Wire BrightData / official bulk exports before production scraping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

# Common entry points (verify current URLs — counties change portals often)
HILLSBOROUGH_CLERK_HOME = "https://www.hillsclerk.com/"
DEFAULT_FILINGS_HINT = (
    "Search Official Records / Court for Lis Pendens and foreclosure filings "
    "in Hillsborough County, then paste the results URL here."
)


@dataclass
class FilingLead:
    case_or_instrument: str
    filing_type: str
    party_name: str
    property_hint: str
    filed_date: str
    source_url: str


def validate_filings_url(url: str) -> dict[str, Any]:
    """Basic URL sanity check before any parse attempt."""
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "Paste a Hillsborough Clerk / filings results URL."}
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"ok": False, "error": "URL must start with http:// or https://"}
    return {
        "ok": True,
        "host": parsed.netloc,
        "path": parsed.path,
        "hint": DEFAULT_FILINGS_HINT,
    }


def prepare_recent_filings_parse(url: str) -> dict[str, Any]:
    """
    Prep step only: fetch headers / sample status so we know the portal is reachable.
    Does not scrape private data or bypass CAPTCHAs.
    """
    check = validate_filings_url(url)
    if not check.get("ok"):
        return check

    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "DealSharkLeadPrep/1.0 (research; contact local ops)"},
            allow_redirects=True,
        )
        return {
            "ok": True,
            "status_code": resp.status_code,
            "final_url": str(resp.url),
            "content_type": resp.headers.get("Content-Type", ""),
            "bytes": len(resp.content),
            "parse_targets": [
                "instrument / case number",
                "filing type (Lis Pendens, Notice of Foreclosure, etc.)",
                "party / defendant names",
                "legal description or parcel if present",
                "filed date",
            ],
            "next_step": (
                "Replace this placeholder with a structured parser once you confirm "
                "the HTML/JSON shape of Recent Filings results. Prefer official APIs "
                "or permitted bulk downloads over brittle scraping."
            ),
            "sample_leads": [],
        }
    except Exception as exc:
        return {"ok": False, "error": f"Could not reach URL: {exc}"}


def mock_tampa_offmarket_leads() -> list[dict[str, str]]:
    """Offline demo leads so the UI section is usable without scraping."""
    return [
        {
            "type": "Lis Pendens",
            "area": "Seminole Heights",
            "note": "Placeholder — replace with live clerk parse",
        },
        {
            "type": "Foreclosure Notice",
            "area": "Ybor City",
            "note": "Placeholder — replace with live clerk parse",
        },
        {
            "type": "Lis Pendens",
            "area": "South Tampa 33606",
            "note": "Flood-risk zip — verify insurance before offer",
        },
    ]
