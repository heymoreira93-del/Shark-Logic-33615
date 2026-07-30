"""
Tampa Data Engine — RentCast live property + comps.

No mock property/comps when the key is missing: callers get None / [] / error.
"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from tampa_config import FLOOD_ZIPS

load_dotenv()

RENTCAST_BASE = "https://api.rentcast.io/v1"


def _headers() -> dict[str, str]:
    key = (os.getenv("RENTCAST_API_KEY") or "").strip()
    return {"accept": "application/json", "X-Api-Key": key}


def has_rentcast_key() -> bool:
    try:
        from secrets_bootstrap import bootstrap_secrets, is_placeholder_secret

        bootstrap_secrets()
        key = (os.getenv("RENTCAST_API_KEY") or "").strip()
        return bool(key) and not is_placeholder_secret(key)
    except Exception:
        key = (os.getenv("RENTCAST_API_KEY") or "").strip()
        return bool(key) and key not in {
            "your_key_here",
            "your_rentcast_key",
            "paste_rentcast_key",
            "",
        }


def extract_zip(address: str, fallback: str = "") -> str:
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", address or "")
    if match:
        return match.group(1)
    return fallback


def geocode_address(address: str) -> dict[str, float] | None:
    """Optional Google Geocoding for lat/lng accuracy."""
    key = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
    if not key or key in {"your_key_here", "your_google_maps_key"}:
        return None
    try:
        url = (
            "https://maps.googleapis.com/maps/api/geocode/json"
            f"?address={quote(address)}&key={key}"
        )
        data = requests.get(url, timeout=20).json()
        results = data.get("results") or []
        if not results:
            return None
        loc = results[0]["geometry"]["location"]
        return {"lat": float(loc["lat"]), "lng": float(loc["lng"])}
    except Exception as exc:
        print(f"Geocode error: {exc}")
        return None


def get_property_data(address: str) -> dict[str, Any] | None:
    """
    Fetch propertyType, squareFootage, yearBuilt, lastSalePrice for an address.
    """
    address = (address or "").strip()
    if not address:
        return None

    if not has_rentcast_key():
        return None

    try:
        url = f"{RENTCAST_BASE}/properties?address={quote(address)}"
        resp = requests.get(url, headers=_headers(), timeout=25)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list):
            if not payload:
                return None
            prop = payload[0]
        elif isinstance(payload, dict):
            prop = payload
        else:
            return None

        last_sale = prop.get("lastSalePrice") or prop.get("lastSale", {})
        if isinstance(last_sale, dict):
            last_sale_price = last_sale.get("price") or 0
        else:
            last_sale_price = last_sale or 0

        return {
            "address": address,
            "propertyType": prop.get("propertyType") or prop.get("propertyUse") or "",
            "squareFootage": float(prop.get("squareFootage") or prop.get("livingArea") or 0),
            "yearBuilt": prop.get("yearBuilt") or prop.get("year_built"),
            "lastSalePrice": float(last_sale_price or 0),
            "zipCode": str(prop.get("zipCode") or extract_zip(address)),
            "bedrooms": prop.get("bedrooms"),
            "bathrooms": prop.get("bathrooms"),
            "raw": prop,
            "source": "rentcast",
        }
    except Exception as exc:
        print(f"RentCast property error: {exc}")
        return None


def get_tampa_comps(address: str, zip_code: str = "", radius_miles: float = 2.0) -> list[dict[str, Any]]:
    """
    Recent sold comps within radius (default 2 miles).
    Uses RentCast /properties + saleDateRange (true solds), not active listings.
    Without RENTCAST_API_KEY: empty list + last_error (never invents solds).
    """
    address = (address or "").strip()
    zip_code = zip_code or extract_zip(address)
    get_tampa_comps.last_error = ""  # type: ignore[attr-defined]
    if not has_rentcast_key():
        get_tampa_comps.last_error = (  # type: ignore[attr-defined]
            "RENTCAST_API_KEY not configured — live comps OFF."
        )
        return []

    try:
        # RentCast: radius requires address OR lat/lng — zip+radius alone returns 400.
        params: dict[str, Any] = {
            "limit": 10,
            "saleDateRange": 365,
        }
        geo = geocode_address(address) if address else None
        if geo:
            params["latitude"] = geo["lat"]
            params["longitude"] = geo["lng"]
            params["radius"] = radius_miles
        elif address:
            params["address"] = address
            params["radius"] = radius_miles
        elif zip_code:
            params["zipCode"] = zip_code
        else:
            params["city"] = "Tampa"
            params["state"] = "FL"

        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        url = f"{RENTCAST_BASE}/properties?{query}"
        resp = requests.get(url, headers=_headers(), timeout=25)
        resp.raise_for_status()
        payload = resp.json()
        listings = payload if isinstance(payload, list) else payload.get("properties") or []

        comps: list[dict[str, Any]] = []
        for item in listings:
            price = float(item.get("lastSalePrice") or item.get("price") or 0)
            sqft = float(item.get("squareFootage") or item.get("livingArea") or 0)
            if price <= 0:
                continue
            comps.append(
                {
                    "address": item.get("formattedAddress")
                    or item.get("addressLine1")
                    or item.get("address")
                    or "Comp",
                    "sold_price": price,
                    "status": "Sold",
                    "distance": f"{item.get('distance', radius_miles)} mi",
                    "beds": item.get("bedrooms") or "?",
                    "baths": item.get("bathrooms") or "?",
                    "sqft": int(sqft) if sqft else 0,
                    "price_per_sqft": (price / sqft) if sqft else 0,
                    "sale_date": item.get("lastSaleDate") or "",
                }
            )
        # Live mode: never invent mock solds when the key is present.
        # Empty list = thin market / API miss — UI should say so, not fake ARV.
        return comps[:10]
    except Exception as exc:
        try:
            print(f"RentCast comps error: {exc}")
        except Exception:
            pass
        get_tampa_comps.last_error = str(exc)  # type: ignore[attr-defined]
        return []


get_tampa_comps.last_error = ""  # type: ignore[attr-defined]


def estimate_arv_from_comps(sqft: float, comps: list[dict[str, Any]]) -> tuple[float, float]:
    """Average $/sqft from comps * subject sqft → ARV."""
    pps: list[float] = []
    for c in comps:
        if c.get("price_per_sqft"):
            pps.append(float(c["price_per_sqft"]))
        elif c.get("sold_price") and c.get("sqft"):
            pps.append(float(c["sold_price"]) / float(c["sqft"]))
    if not pps or not sqft:
        return 0.0, 0.0
    avg = sum(pps) / len(pps)
    return avg * float(sqft), avg


def get_tampa_data(address: str) -> dict[str, Any]:
    """
    Full Tampa pull: property details + comps + ARV from $/sqft.
    """
    address = (address or "").strip()
    if not address:
        return {"error": "Enter an address."}

    if not has_rentcast_key():
        return {
            "error": "RentCast OFF — set RENTCAST_API_KEY for live property/comps. No mock data.",
            "source": "off",
            "comps": [],
            "comps_live": False,
        }

    prop = get_property_data(address)
    if not prop:
        return {"error": "Property not found. Double-check the address (include city/state/zip)."}

    sqft = float(prop.get("squareFootage") or 0)
    zip_code = str(prop.get("zipCode") or extract_zip(address))
    comps = get_tampa_comps(address, zip_code=zip_code)
    arv, avg_pps = estimate_arv_from_comps(sqft, comps)

    # If comps thin, fall back to last sale * 1.15 as rough ARV estimate (live data only)
    if arv <= 0 and prop.get("lastSalePrice"):
        arv = float(prop["lastSalePrice"]) * 1.15
        avg_pps = (arv / sqft) if sqft else 0

    source = prop.get("source", "rentcast")
    return {
        "address": address,
        "yearBuilt": prop.get("yearBuilt"),
        "sqft": sqft,
        "propertyType": prop.get("propertyType"),
        "lastSalePrice": prop.get("lastSalePrice"),
        "zipCode": zip_code,
        "arv": round(arv, 2),
        "avg_sqft_price": round(avg_pps, 2),
        "comps": comps,
        "comps_live": True,
        "comps_empty": not comps,
        "flood_risk": zip_code in FLOOD_ZIPS,
        "source": source,
    }
