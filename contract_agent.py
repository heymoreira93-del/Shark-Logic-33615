"""
Contract Agent — hunt → People Data → price → PDF → deal → queue SMS (HITL).

Does NOT send Twilio SMS. Human taps Send in War Room Offer Queue.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from comms import offer_sms_body
from data_engine import get_tampa_data, has_rentcast_key
from database import (
    enqueue_offer,
    get_agent_candidate_leads,
    init_db,
    update_lead_phone,
)
from db import create_deal
from generator import generate_contract
from phone_enrich import enrich_phone, people_data_configured
from rehab import apply_tampa_risk_adjustments, shark_mao
from seller_factory import hunt_sellers
from tampa_config import MIN_WHOLESALE_FEE


def run_contract_agent(
    *,
    zip_code: str = "33615",
    limit: int = 10,
    fee: float = MIN_WHOLESALE_FEE,
    buyer_name: str = "DealShark",
    market_factor: float = 0.70,
    default_rehab: float = 25000.0,
    emd: float = 1000.0,
    hunt: bool = True,
    absentee_only: bool = True,
) -> dict[str, Any]:
    """
    Prepare queued cash offers for human approval.

    Returns summary: hunted, enriched, queued, skipped, errors, details.
    """
    init_db()
    zip_code = (zip_code or "33615").strip()[:5]
    limit = max(1, min(int(limit), 25))
    fee = max(float(fee), MIN_WHOLESALE_FEE)
    buyer = (buyer_name or "DealShark").strip() or "DealShark"

    summary: dict[str, Any] = {
        "ok": False,
        "hunted": 0,
        "enriched": 0,
        "queued": 0,
        "skipped": 0,
        "errors": [],
        "details": [],
        "zip_code": zip_code,
    }

    if not people_data_configured():
        summary["errors"].append(
            "People-Data OFF — set PEOPLE_DATA_API_URL and PEOPLE_DATA_API_KEY "
            "before running the Contract Agent."
        )
        return summary

    if hunt:
        if not has_rentcast_key():
            summary["errors"].append(
                "RentCast OFF — cannot hunt. Add RENTCAST_API_KEY or uncheck Hunt "
                "to process existing New Leads only."
            )
        else:
            hunt_result = hunt_sellers(
                zip_code=zip_code,
                limit=limit,
                absentee_only=absentee_only,
                fee=fee,
                market_factor=market_factor,
                default_rehab=default_rehab,
                save=True,
            )
            if not hunt_result.get("ok"):
                summary["errors"].append(
                    f"Hunt failed: {hunt_result.get('error') or 'unknown error'}"
                )
            else:
                summary["hunted"] = int(hunt_result.get("saved") or 0)

    candidates = get_agent_candidate_leads(zip_code=zip_code, limit=limit)
    if not candidates:
        summary["errors"].append(
            f"No New Lead candidates in zip {zip_code} ready to queue "
            "(already queued/sent, or hunt returned nothing)."
        )
        summary["ok"] = summary["hunted"] > 0 and not summary["errors"][:1]
        # Still ok=False when nothing to queue
        return summary

    closing = (date.today() + timedelta(days=30)).isoformat()

    for lead in candidates:
        lead_id = int(lead["id"])
        address = (lead.get("address") or "").strip()
        seller_name = (lead.get("seller_name") or "").strip() or "Seller"
        detail: dict[str, Any] = {
            "lead_id": lead_id,
            "address": address,
            "status": "",
            "error": "",
        }

        if not address:
            enqueue_offer(
                lead_id=lead_id,
                deal_id="",
                address="",
                phone="",
                seller_name=seller_name,
                offer_price=0,
                pdf_path="",
                sms_preview="",
                status="SKIPPED",
                error="Missing address",
            )
            summary["skipped"] += 1
            detail["status"] = "SKIPPED"
            detail["error"] = "Missing address"
            summary["details"].append(detail)
            continue

        phone = (lead.get("seller_phone") or "").strip()
        if not phone:
            enrich = enrich_phone(owner_name=seller_name, address=address)
            phone = (enrich.get("phone") or "").strip()
            if phone:
                update_lead_phone(lead_id, phone)
                summary["enriched"] += 1
            else:
                err = enrich.get("error") or "No phone from People Data"
                enqueue_offer(
                    lead_id=lead_id,
                    deal_id="",
                    address=address,
                    phone="",
                    seller_name=seller_name,
                    offer_price=float(lead.get("mao") or 0),
                    pdf_path="",
                    sms_preview="",
                    status="SKIPPED",
                    error=err,
                )
                summary["skipped"] += 1
                detail["status"] = "SKIPPED"
                detail["error"] = err
                summary["details"].append(detail)
                continue
        else:
            # Already had a phone — count as enriched for pipeline clarity
            summary["enriched"] += 1

        # Price: prefer live RentCast ARV when available
        arv = float(lead.get("arv") or 0)
        rehab = float(default_rehab)
        comps: list[dict[str, Any]] = []
        flood_risk = bool(lead.get("flood_risk"))
        z = str(lead.get("zip_code") or zip_code)[:5]

        if has_rentcast_key():
            try:
                live = get_tampa_data(address)
                if live and not live.get("error"):
                    if float(live.get("arv") or 0) > 0:
                        arv = float(live["arv"])
                    comps = live.get("comps") or []
                    z = str(live.get("zipCode") or live.get("zip_code") or z)[:5]
                    if live.get("flood_risk"):
                        flood_risk = True
            except Exception as exc:
                summary["errors"].append(f"{address}: live data miss ({exc})")

        if arv <= 0:
            arv = 250000.0

        offers = shark_mao(
            arv,
            rehab,
            fee,
            market_factor,
            flood_buffer=0.0,
        )
        hazard = apply_tampa_risk_adjustments(z, float(offers["Aggressive"]))
        offer_price = float(hazard["adjusted_mao"])
        flood_risk = flood_risk or bool(hazard.get("is_flood_zip"))
        if offer_price <= 0:
            err = "MAO calculated to $0 or below — skipped"
            enqueue_offer(
                lead_id=lead_id,
                deal_id="",
                address=address,
                phone=phone,
                seller_name=seller_name,
                offer_price=0,
                pdf_path="",
                sms_preview="",
                status="SKIPPED",
                error=err,
            )
            summary["skipped"] += 1
            detail["status"] = "SKIPPED"
            detail["error"] = err
            summary["details"].append(detail)
            continue

        try:
            pdf_path = generate_contract(
                address=address,
                seller=seller_name,
                price=offer_price,
                emd=float(emd),
                closing_date=closing,
                buyer=buyer,
                comps=comps,
                rehab_total=rehab,
                arv=arv,
                flood_insurance_required=flood_risk,
            )
            pdf_str = str(pdf_path)
        except Exception as exc:
            err = f"PDF failed: {exc}"
            enqueue_offer(
                lead_id=lead_id,
                deal_id="",
                address=address,
                phone=phone,
                seller_name=seller_name,
                offer_price=offer_price,
                pdf_path="",
                sms_preview="",
                status="FAILED",
                error=err,
            )
            summary["errors"].append(f"{address}: {err}")
            detail["status"] = "FAILED"
            detail["error"] = err
            summary["details"].append(detail)
            continue

        deal_id = create_deal(
            address,
            offer_price,
            seller_name,
            seller_phone=phone,
            buyer_name=buyer,
            emd=float(emd),
            closing_date=closing,
            pdf_path=pdf_str,
            lead_temp="Warm",
            lead_id=lead_id,
        )

        preview = offer_sms_body(
            address=address,
            price=offer_price,
            seller_name=seller_name,
            buyer_name=buyer,
            deal_id=deal_id,
        )

        qid = enqueue_offer(
            lead_id=lead_id,
            deal_id=deal_id,
            address=address,
            phone=phone,
            seller_name=seller_name,
            offer_price=offer_price,
            pdf_path=pdf_str,
            sms_preview=preview,
            status="QUEUED",
        )
        summary["queued"] += 1
        detail["status"] = "QUEUED"
        detail["deal_id"] = deal_id
        detail["queue_id"] = qid
        detail["offer_price"] = offer_price
        detail["phone"] = phone
        summary["details"].append(detail)

    summary["ok"] = summary["queued"] > 0
    return summary
