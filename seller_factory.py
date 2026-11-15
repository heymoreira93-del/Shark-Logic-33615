"""
Seller Factory — generate War Room leads from RentCast (no BatchData).

Pulls Single Family homes in a target zip (default 33615), prefers absentee
owners (ownerOccupied=false), attaches owner name/mailing, estimates MAO,
and saves into tampa_leads.db.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlencode

import requests
from dotenv import load_dotenv

from blueprint import score_zombie_lead
from data_engine import extract_zip, has_rentcast_key
from database import address_already_active, init_db, save_lead
from rehab import apply_tampa_risk_adjustments, shark_mao
from skip_provider import _owner_from_prop
from tampa_config import DEFAULT_CLOSING_COST_PCT, MIN_WHOLESALE_FEE

load_dotenv()

RENTCAST_BASE = "https://api.rentcast.io/v1"

# Corporate / SFR landlords — not mom-and-pop wholesale zombies
_INSTITUTIONAL_NAME_MARKERS = (
    " LLC",
    " L.L.C",
    " LP",
    " L.P",
    " INC",
    " CORP",
    " TRUST",
    " BORROWER",
    " SFR ",
    "TRICON",
    "INVITATION HOMES",
    " IH BORROWER",
    "PROGRESS RESIDENTIAL",
    "AMH ",
    "AMERICAN HOMES",
    "FIRSTKEY",
    "CERBERUS",
    "BLACKSTONE",
    "HOME PARTNERS",
    "PROPERTY OWNER",
    "HOLDINGS",
    "INVESTMENTS",
    "CAPITAL",
    "FUND ",
    " REIT",
    "BANK ",
    "N.A.",
    "NATIONAL ASSOCIATION",
    "FAMILY LAND",
    "LAND TRUST",
    "LIVING TRUST",
)


def is_institutional_owner(name: str) -> bool:
    """True for LLC/LP/trust/SFR-REIT style owners — skip for zombie wholesale hunt."""
    raw = (name or "").strip().upper()
    if not raw:
        return False
    if "OWNER ON FILE" in raw:
        return True
    padded = f" {raw} "
    for marker in _INSTITUTIONAL_NAME_MARKERS:
        if marker.strip().upper() in raw or marker.upper() in padded:
            # Require word-ish match for short tokens like LP / INC at end
            m = marker.strip().upper()
            if m in {"LLC", "L.L.C", "LP", "L.P", "INC", "CORP", "TRUST"}:
                if raw.endswith(m) or f" {m} " in padded or raw.endswith(f" {m}"):
                    return True
                continue
            if m in raw:
                return True
    return False


def _headers() -> dict[str, str]:
    key = (os.getenv("RENTCAST_API_KEY") or "").strip()
    return {"accept": "application/json", "X-Api-Key": key}


def hunt_sellers(
    *,
    zip_code: str = "33615",
    limit: int = 25,
    absentee_only: bool = True,
    skip_institutions: bool = True,
    property_type: str = "Single Family",
    fee: float = MIN_WHOLESALE_FEE,
    market_factor: float = 0.70,
    default_rehab: float = 25000.0,
    save: bool = True,
) -> dict[str, Any]:
    """
    Query RentCast for properties in zip, score as seller leads, optionally save.
    Returns {ok, leads, saved, skipped_institutions, error}.
    """
    zip_code = (zip_code or "33615").strip()[:5]
    if not has_rentcast_key():
        return {
            "ok": False,
            "leads": [],
            "saved": 0,
            "skipped_institutions": 0,
            "error": "Set RENTCAST_API_KEY to hunt live sellers.",
        }

    params: dict[str, Any] = {
        "zipCode": zip_code,
        "propertyType": property_type,
        "limit": max(1, min(int(limit), 100)),
        "offset": 0,
    }
    url = f"{RENTCAST_BASE}/properties?{urlencode(params)}"

    try:
        resp = requests.get(url, headers=_headers(), timeout=40)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        return {
            "ok": False,
            "leads": [],
            "saved": 0,
            "skipped_institutions": 0,
            "error": str(exc),
        }

    if isinstance(payload, dict) and "error" in payload:
        return {
            "ok": False,
            "leads": [],
            "saved": 0,
            "skipped_institutions": 0,
            "error": str(payload.get("message") or payload.get("error")),
        }

    rows = payload if isinstance(payload, list) else []
    leads: list[dict[str, Any]] = []
    skipped_institutions = 0

    for prop in rows:
        owner_occupied = prop.get("ownerOccupied")
        if absentee_only and owner_occupied is True:
            continue

        formatted = (
            prop.get("formattedAddress")
            or ", ".join(
                str(x)
                for x in (
                    prop.get("addressLine1"),
                    prop.get("city"),
                    prop.get("state"),
                    prop.get("zipCode"),
                )
                if x
            )
        )
        if not formatted:
            continue

        owner_info = _owner_from_prop(prop, formatted)
        owner_name = owner_info.get("owner_name") or ""
        if skip_institutions and is_institutional_owner(owner_name):
            skipped_institutions += 1
            continue

        z = str(prop.get("zipCode") or extract_zip(formatted) or zip_code)[:5]

        last_sale = prop.get("lastSalePrice") or 0
        if isinstance(last_sale, dict):
            last_sale = last_sale.get("price") or 0
        # Rough ARV: last sale or living-area heuristic
        arv = float(last_sale or 0)
        if arv <= 0:
            sqft = float(prop.get("squareFootage") or prop.get("livingArea") or 0)
            arv = sqft * 180.0 if sqft else 250000.0

        offers = shark_mao(
            arv,
            default_rehab,
            fee,
            market_factor,
            flood_buffer=0.0,
            closing_cost_pct=DEFAULT_CLOSING_COST_PCT,
        )
        hazard = apply_tampa_risk_adjustments(z, float(offers["Aggressive"]))
        mao = float(hazard["adjusted_mao"])

        motive = []
        absentee = owner_occupied is False
        if absentee:
            motive.append("Absentee owner")
        if owner_occupied is None:
            motive.append("Owner-occupy unknown")
        if hazard.get("is_flood_zip"):
            motive.append(hazard.get("risk_level") or "Flood zip")
        year = prop.get("yearBuilt")
        if year and int(year) < 1980:
            motive.append(f"Built {year}")

        mailing = owner_info.get("mailing_address") or ""
        # Vacant/zombie look proxy: absentee AND mailing differs from subject
        vacant_proxy = bool(
            absentee
            and mailing
            and mailing.split(",")[0].strip().lower()
            != (formatted.split(",")[0].strip().lower())
        )
        if vacant_proxy:
            motive.append("Mailing != subject (possible vacant)")

        last_sale_f = float(last_sale or 0)
        equity_proxy = max(0.0, arv - last_sale_f) if last_sale_f else 0.0
        scored = score_zombie_lead(
            vacant=vacant_proxy,
            absentee=absentee,
            estimated_equity=equity_proxy,
            owner_contact_status="Mailing Only" if mailing else "Unknown",
            arv=arv,
            mao=mao,
        )

        lead = {
            "address": formatted,
            "zip_code": z,
            "arv": round(arv, 2),
            "mao": round(mao, 2),
            "fee": float(fee),
            "risk": hazard.get("risk_level") or "Standard",
            "flood_risk": bool(hazard.get("is_flood_zip")),
            "seller_name": owner_name,
            "seller_phone": "",
            "mailing_address": mailing,
            "owner_occupied": owner_occupied,
            "vacant": vacant_proxy,
            "absentee": absentee,
            "last_sale_price": last_sale_f,
            "estimated_equity": round(equity_proxy, 2),
            "repairs_estimate": float(default_rehab),
            "owner_contact_status": "Mailing Only" if mailing else "Unknown",
            "motivation_score": scored["motivation_score"],
            "motivation_tier": scored["tier"],
            "motive_tags": ", ".join(scored["tags"] or motive) or "Zip hunt",
            "motive": ", ".join(motive) or "Zip hunt",
            "status": "New Lead",
            "source": "seller_factory",
        }
        leads.append(lead)

    saved = 0
    skipped_dupes = 0
    if save and leads:
        init_db()
        for lead in leads:
            if address_already_active(lead["address"]):
                skipped_dupes += 1
                continue
            save_lead(
                address=lead["address"],
                zip_code=lead["zip_code"],
                arv=lead["arv"],
                mao=lead["mao"],
                fee=lead["fee"],
                risk=lead["risk"],
                flood_risk=lead["flood_risk"],
                status="New Lead",
                seller_name=lead["seller_name"],
                seller_phone="",
                mailing_address=lead.get("mailing_address") or "",
                vacant=bool(lead.get("vacant")),
                absentee=bool(lead.get("absentee")),
                owner_occupied=lead.get("owner_occupied"),
                last_sale_price=float(lead.get("last_sale_price") or 0),
                estimated_equity=float(lead.get("estimated_equity") or 0),
                repairs_estimate=float(lead.get("repairs_estimate") or 0),
                owner_contact_status=lead.get("owner_contact_status") or "Unknown",
                motivation_score=int(lead.get("motivation_score") or 0),
                motivation_tier=lead.get("motivation_tier") or "",
                motive_tags=lead.get("motive_tags") or "",
            )
            saved += 1

    return {
        "ok": True,
        "leads": leads,
        "saved": saved,
        "skipped_institutions": skipped_institutions,
        "skipped_dupes": skipped_dupes,
        "error": "",
        "queried": len(rows),
        "zip_code": zip_code,
    }


def render_seller_factory(
    *,
    fee: float = MIN_WHOLESALE_FEE,
    market_factor: float = 0.70,
) -> None:
    """Streamlit UI for Seller Factory tab."""
    import streamlit as st

    st.subheader("Seller Factory")
    st.caption(
        "Pulls live property + owner names from RentCast into your War Room. "
        "Skips LLC / SFR / bank / trust owners by default (not mom-and-pop zombies). "
        "Cell phones are not in RentCast; paste mobiles when you get them."
    )

    if not has_rentcast_key():
        st.error("Add RENTCAST_API_KEY in `.env` / Streamlit Secrets to hunt.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        zip_code = st.text_input("Target Zip", value="33615", key="sf_zip")
    with c2:
        limit = st.number_input("Max leads", 5, 100, 25, 5, key="sf_limit")
    with c3:
        rehab = st.number_input("Default rehab $", 5000, 100000, 25000, 1000, key="sf_rehab")
    with c4:
        absentee_only = st.checkbox("Absentee only", value=True, key="sf_absentee")
    skip_institutions = st.checkbox(
        "Skip LLC / institutional owners",
        value=True,
        key="sf_skip_inst",
        help="Filters Invitation Homes, Tricon, banks, trusts, LLCs — keep people you can call.",
    )

    if st.button("HUNT SELLERS → WAR ROOM", type="primary", use_container_width=True):
        with st.spinner(f"Hunting {zip_code}..."):
            result = hunt_sellers(
                zip_code=zip_code.strip(),
                limit=int(limit),
                absentee_only=bool(absentee_only),
                skip_institutions=bool(skip_institutions),
                fee=float(fee),
                market_factor=float(market_factor),
                default_rehab=float(rehab),
                save=True,
            )
        if not result.get("ok"):
            st.error(result.get("error") or "Hunt failed")
            return
        skipped = int(result.get("skipped_institutions") or 0)
        st.success(
            f"Found {len(result['leads'])} people lead(s) from {result.get('queried', 0)} "
            f"records · saved {result['saved']} · skipped {skipped} institutional."
        )
        if result["leads"]:
            st.dataframe(
                [
                    {
                        "Address": L["address"],
                        "Owner": L["seller_name"],
                        "ARV": L["arv"],
                        "MAO": L["mao"],
                        "Why": L["motive"],
                        "Mailing": L["mailing_address"],
                    }
                    for L in result["leads"]
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.info(
                "Next: open **Tampa War Room**, skip-trace/paste phones, then Fire SMS / follow-up."
            )
        else:
            st.warning(
                "No matches. Try turning off Absentee only, or another nearby zip "
                "(33634, 33614, 33607)."
            )
