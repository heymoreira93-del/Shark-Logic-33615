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
    account_sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    if not account_sid or not auth_token:
        raise RuntimeError("Missing TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN in .env / secrets")
    return Client(account_sid, auth_token)


def _from_number() -> str:
    from_phone = _normalize_e164(os.getenv("TWILIO_PHONE_NUMBER", ""))
    if not from_phone:
        raise RuntimeError("Missing TWILIO_PHONE_NUMBER in .env / secrets")
    return from_phone


def signing_url(deal_id: str) -> str:
    base = os.getenv("APP_BASE_URL", "http://localhost:8501").rstrip("/")
    return f"{base}/?deal_id={deal_id}"


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
        )

    first = seller.split()[0] if seller else "there"
    body = (
        f"Hi {first}, I'm {buyer_name}. "
        f"I just saw {address} and wanted to see if you'd consider a cash offer? "
        f"I have a contract ready to go at ${price:,.0f}."
    )
    if deal_id:
        body += f" View and sign the agreement here: {signing_url(deal_id)}"

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

def notify_deal_signed(
    *,
    address: str,
    price: float,
    signature_name: str,
    deal_id: str,
) -> Optional[str]:
    """Alert your phone when a seller click-signs."""
    notify_to = _normalize_e164(os.getenv("NOTIFY_PHONE", ""))
    if not notify_to:
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
        return message.sid
    except Exception as exc:
        print(f"Error notifying signed deal: {exc}")
        return None


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
