"""
Twilio click-to-call — dials your phone and the lead into a conference.
Uses TWILIO_VOICE_WEBHOOK (Twilio Function) when set; otherwise inline TwiML Dial.
"""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

# Default from your Twilio Function
DEFAULT_VOICE_WEBHOOK = "https://conference-6357-gpuam0.twil.io/conference"


def _normalize_e164(phone: str) -> str:
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
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    if not sid or not token:
        raise RuntimeError("Missing TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN")
    return Client(sid, token)


def _from_number() -> str:
    from_phone = _normalize_e164(os.getenv("TWILIO_PHONE_NUMBER", ""))
    if not from_phone:
        raise RuntimeError("Missing TWILIO_PHONE_NUMBER")
    return from_phone


def agent_phone() -> str:
    """Your phone — rings first on click-to-call. Prefers TWILIO_AGENT_PHONE, then NOTIFY_PHONE."""
    return _normalize_e164(
        os.getenv("TWILIO_AGENT_PHONE")
        or os.getenv("NOTIFY_PHONE")
        or ""
    )


def _is_placeholder_phone(phone: str) -> bool:
    """True for fake/demo numbers (e.g. +1555...) that Twilio will reject."""
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    # NANP 555-01xx is reserved fiction; also catch bare +1555...
    return len(digits) == 10 and digits.startswith("555")


def voice_webhook() -> str:
    return (os.getenv("TWILIO_VOICE_WEBHOOK") or DEFAULT_VOICE_WEBHOOK).strip()


def voice_configured() -> bool:
    try:
        you = agent_phone()
        return bool(
            (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
            and (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
            and _from_number()
            and you
            and not _is_placeholder_phone(you)
        )
    except Exception:
        return False


def _friendly_twilio_error(exc: BaseException) -> str:
    msg = str(exc)
    low = msg.lower()
    if "unverified" in low or "trial" in low:
        return (
            "Twilio trial: verify your cell in Console, or set TWILIO_AGENT_PHONE / "
            "NOTIFY_PHONE to a verified E.164 number (+1...)."
        )
    if "not a valid" in low or ("invalid" in low and "phone" in low):
        return (
            "Invalid agent/lead phone. Set TWILIO_AGENT_PHONE or NOTIFY_PHONE to your "
            "real cell in E.164 (+1...)."
        )
    if _is_placeholder_phone(agent_phone()):
        return (
            "Agent phone looks like a placeholder. Set TWILIO_AGENT_PHONE or NOTIFY_PHONE "
            "to your real cell (E.164)."
        )
    return msg


def click_to_call(
    lead_phone: str,
    *,
    agent: str | None = None,
    label: str = "",
) -> dict[str, Any]:
    """
    Ring YOUR phone, then connect the lead (conference webhook or direct Dial).

    Returns {ok, agent_sid, lead_sid, error, mode}.
    """
    lead = _normalize_e164(lead_phone)
    you = _normalize_e164(agent or agent_phone())
    if not lead:
        return {"ok": False, "error": "Lead phone missing (+1...)", "mode": ""}
    if not you:
        return {
            "ok": False,
            "error": "Set TWILIO_AGENT_PHONE or NOTIFY_PHONE to your cell (+1...)",
            "mode": "",
        }
    if _is_placeholder_phone(you):
        return {
            "ok": False,
            "error": (
                "Agent phone is a placeholder (+1555...). Set TWILIO_AGENT_PHONE or "
                "NOTIFY_PHONE to your real cell in E.164."
            ),
            "mode": "",
        }
    if lead == you:
        return {"ok": False, "error": "Lead phone cannot match your agent phone", "mode": ""}

    from_n = _from_number()
    client = _client()
    webhook = voice_webhook()
    room = f"shark-{int(time.time())}"
    if label:
        safe = "".join(c if c.isalnum() else "-" for c in label)[:40]
        room = f"shark-{safe}-{int(time.time()) % 100000}"

    try:
        # Prefer your Twilio Function conference webhook for both legs
        if webhook:
            # Pass room name if the Function supports it (harmless otherwise)
            sep = "&" if "?" in webhook else "?"
            url_agent = f"{webhook}{sep}conference={quote(room)}&role=agent"
            url_lead = f"{webhook}{sep}conference={quote(room)}&role=lead"

            agent_call = client.calls.create(
                to=you,
                from_=from_n,
                url=url_agent,
                method="POST",
            )
            lead_call = client.calls.create(
                to=lead,
                from_=from_n,
                url=url_lead,
                method="POST",
            )
            return {
                "ok": True,
                "mode": "conference_webhook",
                "agent_sid": agent_call.sid,
                "lead_sid": lead_call.sid,
                "room": room,
                "error": "",
                "message": f"Calling you at {you}, then connecting lead {lead}. Answer your phone.",
            }

        # Fallback: call you, then dial the lead when you answer
        twiml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response>"
            f"<Say>Connecting you to the lead. One moment.</Say>"
            f'<Dial callerId="{from_n}"><Number>{lead}</Number></Dial>'
            f"</Response>"
        )
        agent_call = client.calls.create(
            to=you,
            from_=from_n,
            twiml=twiml,
        )
        return {
            "ok": True,
            "mode": "direct_dial",
            "agent_sid": agent_call.sid,
            "lead_sid": "",
            "room": "",
            "error": "",
            "message": f"Calling you at {you}. Answer to connect to {lead}.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": _friendly_twilio_error(exc),
            "mode": "",
            "agent_sid": "",
            "lead_sid": "",
        }
