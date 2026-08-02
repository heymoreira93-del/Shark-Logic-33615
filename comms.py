"""
Twilio SMS engine — create deal first, then text the signing link.
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from twilio.rest import Client

from db import create_deal

load_dotenv()


def _ensure_secrets() -> None:
    try:
        from secrets_bootstrap import bootstrap_secrets

        bootstrap_secrets()
    except Exception:
        pass


def _normalize_e164(phone: str) -> str:
    """Fix common typos like ++1... and bare 10-digit US numbers."""
    p = (phone or "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if p.startswith("++"):
        p = "+" + p[2:]
    if p and not p.startswith("+") and p.isdigit():
        if len(p) == 10:
            p = "+1" + p
        elif len(p) == 11 and p.startswith("1"):
            p = "+" + p
    return p


def _client() -> Client:
    _ensure_secrets()
    account_sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    try:
        from secrets_bootstrap import is_placeholder_secret

        if is_placeholder_secret(account_sid) or is_placeholder_secret(auth_token):
            raise RuntimeError(
                "Twilio secrets look like placeholders — paste real TWILIO_* keys"
            )
    except ImportError:
        pass
    if not account_sid or not auth_token:
        raise RuntimeError("Missing TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN in .env / secrets")
    return Client(account_sid, auth_token)


def _from_number() -> str:
    _ensure_secrets()
    from_phone = _normalize_e164(os.getenv("TWILIO_PHONE_NUMBER", ""))
    if not from_phone:
        raise RuntimeError("Missing TWILIO_PHONE_NUMBER in .env / secrets")
    try:
        from secrets_bootstrap import is_placeholder_secret

        if is_placeholder_secret(from_phone) or from_phone.upper().endswith("XXXXXXXXXX"):
            raise RuntimeError("TWILIO_PHONE_NUMBER is still a placeholder")
    except ImportError:
        pass
    return from_phone


def signing_url(deal_id: str) -> str:
    try:
        from secrets_bootstrap import app_base_url

        base = app_base_url()
    except Exception:
        base = (os.getenv("APP_BASE_URL") or "https://realestateshark.streamlit.app").rstrip("/")
    return f"{base}/?deal_id={deal_id}"


def offer_sms_body(
    *,
    address: str,
    price: float,
    seller_name: str = "",
    buyer_name: str = "an investor",
    deal_id: str | None = None,
) -> str:
    """Same SMS text used for queue preview and live send."""
    seller = (seller_name or "Seller").strip()
    first = seller.split()[0] if seller else "there"
    body = (
        f"Hi {first}, I'm {buyer_name}. "
        f"I just saw {address} and wanted to see if you'd consider a cash offer? "
        f"I have a contract ready to go at ${price:,.0f}."
    )
    if deal_id:
        body += f" View and sign the agreement here: {signing_url(deal_id)}"
    return body


def send_offer_sms(
    to_phone: str,
    address: str,
    price: float,
    *,
    deal_id: str | None = None,
    seller_name: str = "",
    buyer_name: str = "an investor",
    create_if_missing: bool = True,
    pdf_path: str = "",
    emd: float = 1000.0,
    closing_date: str = "",
    lead_temp: str = "Warm",
    lead_id: int | None = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Generate a DB deal (if needed), then SMS the seller with the live signing URL.

    Returns (message_sid, deal_id). Either may be None on failure.
    """
    to_phone = _normalize_e164(to_phone)
    if not to_phone:
        print("Error firing SMS: empty phone number")
        return None, deal_id

    seller = (seller_name or "Seller").strip()
    if not deal_id and create_if_missing:
        deal_id = create_deal(
            address,
            price,
            seller,
            seller_phone=to_phone,
            buyer_name=buyer_name,
            emd=emd,
            closing_date=closing_date,
            pdf_path=pdf_path,
            lead_temp=lead_temp,
            lead_id=lead_id,
        )

    body = offer_sms_body(
        address=address,
        price=price,
        seller_name=seller,
        buyer_name=buyer_name,
        deal_id=deal_id,
    )

    try:
        message = _client().messages.create(
            body=body,
            from_=_from_number(),
            to=to_phone,
        )
        return message.sid, deal_id
    except Exception as exc:
        print(f"Error firing SMS: {exc}")
        # Stash last error for UI (Streamlit session may read via getattr)
        send_offer_sms.last_error = str(exc)  # type: ignore[attr-defined]
        return None, deal_id


send_offer_sms.last_error = ""  # type: ignore[attr-defined]


def send_queued_offer(
    queue_id: int,
    *,
    buyer_name: str = "DealShark",
) -> dict[str, object]:
    """
    Human-approved send: fire SMS for a QUEUED offer_queue row.
    Does not create a new deal — uses the existing deal_id.
    """
    from database import (
        get_offer_queue_item,
        mark_contacted,
        mark_offer_failed,
        mark_offer_sent,
    )

    row = get_offer_queue_item(int(queue_id))
    if not row:
        return {"ok": False, "error": f"Queue item #{queue_id} not found."}
    if (row.get("status") or "") != "QUEUED":
        return {
            "ok": False,
            "error": f"Queue item #{queue_id} is {row.get('status')}, not QUEUED.",
        }

    phone = (row.get("phone") or "").strip()
    deal_id = (row.get("deal_id") or "").strip()
    address = row.get("address") or ""
    price = float(row.get("offer_price") or 0)
    seller = row.get("seller_name") or ""
    pdf_path = row.get("pdf_path") or ""
    lead_id = row.get("lead_id")

    if not phone:
        mark_offer_failed(int(queue_id), "No phone on queued offer")
        return {"ok": False, "error": "No phone on queued offer."}
    if not deal_id:
        mark_offer_failed(int(queue_id), "Missing deal_id")
        return {"ok": False, "error": "Queued offer is missing deal_id."}

    sid, _ = send_offer_sms(
        phone,
        address,
        price,
        deal_id=deal_id,
        seller_name=seller,
        buyer_name=buyer_name,
        create_if_missing=False,
        pdf_path=pdf_path,
        lead_id=int(lead_id) if lead_id not in (None, "") else None,
    )
    if not sid:
        err = getattr(send_offer_sms, "last_error", "") or "Twilio send failed"
        mark_offer_failed(int(queue_id), err)
        return {"ok": False, "error": err, "deal_id": deal_id}

    mark_offer_sent(int(queue_id))
    if lead_id not in (None, ""):
        try:
            mark_contacted(int(lead_id), status="Offer Sent")
        except Exception:
            pass
    return {"ok": True, "sid": sid, "deal_id": deal_id, "address": address}

def notify_phone() -> str:
    """Your cell for DEAL SIGNED alerts — NOTIFY_PHONE, else TWILIO_AGENT_PHONE."""
    _ensure_secrets()
    for key in ("NOTIFY_PHONE", "TWILIO_AGENT_PHONE"):
        raw = _normalize_e164(os.getenv(key, ""))
        if not raw:
            continue
        try:
            from secrets_bootstrap import is_placeholder_secret

            if is_placeholder_secret(raw):
                continue
        except Exception:
            pass
        # Block obvious placeholders like +1555...
        digits = "".join(c for c in raw if c.isdigit())
        if digits.startswith("1555") or raw.startswith("+1555"):
            continue
        return raw
    return ""


def sign_alerts_configured() -> bool:
    return bool(notify_phone())


def notify_deal_signed(
    *,
    address: str,
    price: float,
    signature_name: str,
    deal_id: str,
) -> Optional[str]:
    """Alert your phone when a seller or assignee click-signs."""
    _ensure_secrets()
    notify_to = notify_phone()
    if not notify_to:
        print("Sign alert skipped — set NOTIFY_PHONE or TWILIO_AGENT_PHONE")
        notify_deal_signed.last_error = (  # type: ignore[attr-defined]
            "Missing NOTIFY_PHONE / TWILIO_AGENT_PHONE"
        )
        return None
    body = (
        f"DEAL SIGNED - {address} @ ${price:,.0f}. "
        f"Signed by {signature_name}. deal_id={deal_id}"
    )
    try:
        message = _client().messages.create(
            body=body,
            from_=_from_number(),
            to=notify_to,
        )
        notify_deal_signed.last_error = ""  # type: ignore[attr-defined]
        return message.sid
    except Exception as exc:
        print(f"Error notifying signed deal: {exc}")
        notify_deal_signed.last_error = str(exc)  # type: ignore[attr-defined]
        return None


notify_deal_signed.last_error = ""  # type: ignore[attr-defined]


def send_followup_sms(
    to_phone: str,
    address: str,
    *,
    seller_name: str = "",
    buyer_name: str = "DealShark",
    mao: float | None = None,
    status: str = "",
    zip_code: str = "",
) -> Optional[str]:
    """
    War Room follow-up. Lis Pendens + 33615 get specialized scripts.
    """
    to_phone = _normalize_e164(to_phone)
    if not to_phone:
        print("Error follow-up SMS: empty phone")
        return None

    first = (seller_name or "there").strip().split()[0]
    z = (zip_code or "").strip()[:5]
    if (status or "").strip() == "Lis Pendens":
        body = (
            f"Hi {first}, I'm {buyer_name}. "
            f"I saw what's going on with the county filing on {address} — "
            f"I can help you stop the auction and keep some equity in your pocket. "
            f"Can we talk today?"
        )
    elif z == "33615":
        body = (
            f"Hey! Just drove by your place in 33615. "
            f"I'm looking for a project in Town 'N' Country that I can close "
            f"before the end of the month—no inspections, regardless of the flood zone status. "
            f"Do you have a price in mind for a cash sale?"
        )
    else:
        price_bit = f" around ${mao:,.0f}" if mao else ""
        body = (
            f"Hey {first}, {buyer_name} again on {address}. "
            f"Just checking in — still open to a clean cash offer{price_bit}? "
            f"Happy to move fast if the timing is right."
        )

    try:
        message = _client().messages.create(
            body=body,
            from_=_from_number(),
            to=to_phone,
        )
        return message.sid
    except Exception as exc:
        print(f"Error follow-up SMS: {exc}")
        return None
