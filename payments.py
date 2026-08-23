"""
Stripe EMD checkout — create sessions, verify payment server-side, persist results.

Payment success is NEVER taken from a query flag. Only Stripe session retrieve
(or a verified webhook payload) can mark EMD paid.
"""

from __future__ import annotations

import os
from typing import Any


_STRIPE_PLACEHOLDERS = frozenset(
    {
        "",
        "sk_test_...",
        "sk_live_...",
        "rk_test_...",
        "rk_live_...",
        "your_key_here",
        "sk_live_xxxxxxxx",
        "sk_test_xxxxxxxx",
        "rk_live_xxxxxxxx",
        "rk_test_xxxxxxxx",
    }
)


def _stripe_key() -> str:
    try:
        from secrets_bootstrap import bootstrap_secrets, is_placeholder_secret

        bootstrap_secrets()
        key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
        if is_placeholder_secret(key):
            return ""
        return key
    except Exception:
        key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
        if key in _STRIPE_PLACEHOLDERS or key.endswith("xxxxxxxx"):
            return ""
        return key


def _webhook_secret() -> str:
    try:
        from secrets_bootstrap import bootstrap_secrets, is_placeholder_secret

        bootstrap_secrets()
        raw = (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()
        if is_placeholder_secret(raw):
            return ""
        return raw
    except Exception:
        return (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()


def stripe_configured() -> bool:
    key = _stripe_key()
    return bool(key) and key not in _STRIPE_PLACEHOLDERS


def stripe_mode() -> str:
    """Return 'live', 'test', 'unknown', or 'off'."""
    key = _stripe_key()
    if not key or key in _STRIPE_PLACEHOLDERS:
        return "off"
    if key.startswith("sk_live_") or key.startswith("rk_live_"):
        return "live"
    if key.startswith("sk_test_") or key.startswith("rk_test_"):
        return "test"
    return "unknown"


def publishable_key_configured() -> bool:
    """Hosted Checkout does not require a publishable key. Report presence only."""
    raw = (os.getenv("STRIPE_PUBLISHABLE_KEY") or os.getenv("STRIPE_PUBLIC_KEY") or "").strip()
    return bool(raw) and raw.startswith(("pk_live_", "pk_test_"))


def webhook_secret_configured() -> bool:
    secret = _webhook_secret()
    return bool(secret) and secret.startswith("whsec_")


def webhook_receive_supported() -> bool:
    """Streamlit Community Cloud cannot host a raw Stripe POST webhook endpoint."""
    return False


def emd_amount_cents() -> int:
    """
    Assignment EMD in Stripe cents. Default $2,500.

    Prefers STRIPE_EMD_DOLLARS (e.g. 2500). Also accepts STRIPE_EMD_CENTS.
    Footgun fix: if someone sets STRIPE_EMD_CENTS=2500 meaning dollars,
    coerce to 250000 cents (same for other typical dollar EMDs 20–10000).
    """
    try:
        from secrets_bootstrap import bootstrap_secrets

        bootstrap_secrets()
    except Exception:
        pass

    dollars_raw = (os.getenv("STRIPE_EMD_DOLLARS") or "").strip()
    if dollars_raw:
        try:
            return max(100, int(round(float(dollars_raw) * 100)))
        except ValueError:
            pass

    cents_raw = (os.getenv("STRIPE_EMD_CENTS") or "250000").strip()
    try:
        cents = int(round(float(cents_raw)))
    except ValueError:
        cents = 250_000

    # Legacy $20 EMD (2000 cents) — bump to the live $2,500 default.
    if cents in (20, 2000):
        return 250_000

    # Typical user mistake: typed dollars into STRIPE_EMD_CENTS (2500 → $25).
    # Values 20–9999 are treated as dollars (×100), except 20 handled above.
    if 21 <= cents <= 9999:
        cents = cents * 100
    return max(100, cents)


def emd_amount_dollars() -> float:
    return emd_amount_cents() / 100.0


def _base_url() -> str:
    try:
        from secrets_bootstrap import app_base_url

        return app_base_url()
    except Exception:
        return (os.getenv("APP_BASE_URL") or "https://realestateshark.streamlit.app").rstrip("/")


def _client() -> Any:
    import stripe

    secret = _stripe_key()
    if not secret:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    stripe.api_key = secret
    return stripe


def stripe_account_status() -> dict[str, Any]:
    """
    Safe non-charge probe: charges_enabled, payouts_enabled, bank linked.
    Never includes secret values.
    """
    out: dict[str, Any] = {
        "configured": stripe_configured(),
        "mode": stripe_mode(),
        "charges_enabled": False,
        "payouts_enabled": False,
        "details_submitted": False,
        "bank_linked": False,
        "bank_count": 0,
        "live_charges_blocked": False,
        "webhook_secret": webhook_secret_configured(),
        "webhook_receive": webhook_receive_supported(),
        "publishable_key": publishable_key_configured(),
        "notes": [],
        "error": "",
    }
    if not stripe_configured():
        out["error"] = "Missing STRIPE_SECRET_KEY"
        out["notes"].append("Set STRIPE_SECRET_KEY in Streamlit Cloud Secrets or local .env")
        return out
    try:
        stripe = _client()
        try:
            stripe.Balance.retrieve()
        except Exception as bal_exc:
            msg = str(bal_exc).lower()
            code = getattr(bal_exc, "code", "") or ""
            status = getattr(bal_exc, "http_status", "") or ""
            if "cannot currently make live charges" in msg:
                out["live_charges_blocked"] = True
                out["error"] = "Stripe account cannot make live charges yet"
            else:
                out["error"] = f"Stripe API probe failed (http={status or '?'} code={code or 'n/a'})"
            return out
        acct = stripe.Account.retrieve()
        out["charges_enabled"] = bool(acct.get("charges_enabled"))
        out["payouts_enabled"] = bool(acct.get("payouts_enabled"))
        out["details_submitted"] = bool(acct.get("details_submitted"))
        banks = 0
        try:
            ext2 = stripe.Account.retrieve(expand=["external_accounts"])
            data = (ext2.get("external_accounts") or {}).get("data") or []
            banks = len([x for x in data if (x.get("object") if isinstance(x, dict) else getattr(x, "object", "")) == "bank_account"])
        except Exception:
            banks = 1 if out["payouts_enabled"] else 0
        out["bank_count"] = banks
        out["bank_linked"] = banks > 0 or bool(out["payouts_enabled"])
        if out["mode"] == "live" and not out["charges_enabled"]:
            out["live_charges_blocked"] = True
            out["notes"].append(
                "A) LIVE charges blocked — finish Stripe Dashboard → Activate account "
                "(identity + business). Keep sk_live_... after approval."
            )
        if out["mode"] == "live" and out["charges_enabled"] and not out["payouts_enabled"]:
            out["notes"].append(
                "B) Live charges ON but payouts OFF — add a bank in Stripe → Settings → "
                "Bank accounts and payouts."
            )
        if out["mode"] == "live" and out["charges_enabled"] and out["payouts_enabled"]:
            out["notes"].append(
                "B) Live charges + payouts ON — first real buyer checkout starts the "
                "7–14 day first-payout clock."
            )
        if out["mode"] == "test":
            out["notes"].append(
                "TEST key in use — 4242 card works for E2E; no money hits your bank."
            )
        if not out["webhook_receive"]:
            out["notes"].append(
                "Webhooks: Streamlit Cloud cannot receive Stripe POSTs. "
                "Payment is confirmed by retrieving the Checkout Session on return. "
                "Optional STRIPE_WEBHOOK_SECRET is unused until a dedicated webhook host exists."
            )
        return out
    except Exception as exc:
        msg = str(exc).lower()
        code = getattr(exc, "code", "") or ""
        status = getattr(exc, "http_status", "") or ""
        if "cannot currently make live charges" in msg:
            out["live_charges_blocked"] = True
            out["error"] = "Stripe account cannot make live charges yet"
        else:
            out["error"] = f"Stripe account probe failed (http={status or '?'} code={code or 'n/a'})"
        return out


def create_checkout_session(
    *,
    address: str,
    assignment_fee: float,
    emd_cents: int | None = None,
    success_url: str | None = None,
    cancel_url: str | None = None,
    deal_id: str = "",
) -> str | None:
    """
    Create a Stripe Checkout session for non-refundable EMD.
    Default EMD: $2,500 (or STRIPE_EMD_DOLLARS / STRIPE_EMD_CENTS).
    On failure returns None and sets create_checkout_session.last_error.
    Stores a PENDING payment row when the session is created.
    """
    create_checkout_session.last_error = ""  # type: ignore[attr-defined]
    create_checkout_session.last_session_id = ""  # type: ignore[attr-defined]
    secret = _stripe_key()
    if not secret:
        create_checkout_session.last_error = "Missing STRIPE_SECRET_KEY"  # type: ignore[attr-defined]
        return None

    stripe = _client()
    amount = emd_cents if emd_cents is not None else emd_amount_cents()
    base = _base_url()
    success = success_url or f"{base}/?emd_return=1&session_id={{CHECKOUT_SESSION_ID}}"
    cancel = cancel_url or f"{base}/?emd_cancel=1"

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Deal Assignment EMD - {address[:80]}",
                            "description": (
                                f"Non-refundable earnest money deposit. "
                                f"Assignment fee at closing: ${assignment_fee:,.0f}"
                            ),
                        },
                        "unit_amount": amount,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success,
            cancel_url=cancel,
            client_reference_id=(deal_id or address)[:200],
            metadata={
                "address": address[:500],
                "assignment_fee": str(assignment_fee),
                "deal_id": (deal_id or "")[:64],
            },
        )
        create_checkout_session.last_session_id = session.id  # type: ignore[attr-defined]
        try:
            from db import record_checkout_session

            record_checkout_session(
                stripe_session_id=session.id,
                address=address,
                deal_id=deal_id or "",
                amount_cents=amount,
                mode=stripe_mode(),
                status="PENDING",
                checkout_url=session.url or "",
            )
        except Exception as persist_exc:
            print(f"Payment persist (pending) failed: {persist_exc}")
        return session.url
    except Exception as exc:
        msg = str(exc)
        if "cannot currently make live charges" in msg.lower():
            msg = (
                "Stripe LIVE charges are locked. Finish Activate account / identity "
                "verification in Stripe Dashboard, OR switch STRIPE_SECRET_KEY to "
                "sk_test_... until live is approved."
            )
        create_checkout_session.last_error = msg  # type: ignore[attr-defined]
        print(f"Stripe checkout error: {exc}")
        return None


create_checkout_session.last_error = ""  # type: ignore[attr-defined]
create_checkout_session.last_session_id = ""  # type: ignore[attr-defined]


def _session_to_dict(session: Any) -> dict[str, Any]:
    payment_intent = session.get("payment_intent") if isinstance(session, dict) else getattr(session, "payment_intent", None)
    if hasattr(payment_intent, "id"):
        payment_intent = payment_intent.id
    meta = session.get("metadata") if isinstance(session, dict) else getattr(session, "metadata", None) or {}
    return {
        "id": session.get("id") if isinstance(session, dict) else session.id,
        "payment_status": session.get("payment_status") if isinstance(session, dict) else session.payment_status,
        "status": session.get("status") if isinstance(session, dict) else getattr(session, "status", ""),
        "amount_total": session.get("amount_total") if isinstance(session, dict) else getattr(session, "amount_total", 0),
        "payment_intent": payment_intent or "",
        "url": session.get("url") if isinstance(session, dict) else getattr(session, "url", "") or "",
        "metadata": dict(meta) if meta else {},
        "client_reference_id": (
            session.get("client_reference_id")
            if isinstance(session, dict)
            else getattr(session, "client_reference_id", "")
        )
        or "",
    }


def retrieve_checkout_session(session_id: str) -> dict[str, Any] | None:
    """Fetch a Checkout Session from Stripe. Returns None if missing/invalid."""
    sid = (session_id or "").strip()
    if not sid.startswith("cs_"):
        return None
    try:
        stripe = _client()
        session = stripe.checkout.Session.retrieve(sid)
        return _session_to_dict(session)
    except Exception as exc:
        print(f"Stripe retrieve error: {exc}")
        return None


def session_is_paid(session: dict[str, Any] | None) -> bool:
    if not session:
        return False
    return (session.get("payment_status") or "") == "paid"


def confirm_checkout_session(session_id: str) -> dict[str, Any]:
    """
    Server-side confirmation. Persist only when Stripe says paid.
    Idempotent: re-confirming the same session_id does not duplicate money rows.
    """
    result: dict[str, Any] = {
        "ok": False,
        "paid": False,
        "session_id": (session_id or "").strip(),
        "payment_intent": "",
        "amount_cents": 0,
        "address": "",
        "deal_id": "",
        "mode": stripe_mode(),
        "error": "",
    }
    sid = result["session_id"]
    if not sid.startswith("cs_"):
        result["error"] = "Missing or invalid Stripe session_id"
        return result
    session = retrieve_checkout_session(sid)
    if not session:
        result["error"] = "Could not retrieve Checkout Session from Stripe"
        return result
    meta = session.get("metadata") or {}
    result["address"] = str(meta.get("address") or session.get("client_reference_id") or "")
    result["deal_id"] = str(meta.get("deal_id") or "")
    result["amount_cents"] = int(session.get("amount_total") or 0)
    result["payment_intent"] = str(session.get("payment_intent") or "")
    result["ok"] = True
    if not session_is_paid(session):
        result["error"] = f"Stripe payment_status={session.get('payment_status')!r} (not paid)"
        try:
            from db import record_checkout_session

            record_checkout_session(
                stripe_session_id=sid,
                address=result["address"],
                deal_id=result["deal_id"],
                amount_cents=result["amount_cents"],
                mode=stripe_mode(),
                status=str(session.get("payment_status") or "UNPAID").upper(),
                checkout_url=str(session.get("url") or ""),
                stripe_payment_intent=result["payment_intent"],
            )
        except Exception:
            pass
        return result

    result["paid"] = True
    try:
        from db import mark_emd_paid_from_stripe

        mark_emd_paid_from_stripe(
            stripe_session_id=sid,
            address=result["address"],
            deal_id=result["deal_id"],
            amount_cents=result["amount_cents"],
            mode=stripe_mode(),
            stripe_payment_intent=result["payment_intent"],
        )
    except Exception as exc:
        result["error"] = f"Paid on Stripe but local persist failed: {exc}"
    return result


def verify_webhook_payload(payload: bytes, sig_header: str) -> dict[str, Any]:
    """
    Verify a Stripe webhook signature if STRIPE_WEBHOOK_SECRET is set.
    Streamlit Cloud has no POST endpoint — this is for a future sidecar only.
    """
    secret = _webhook_secret()
    if not secret:
        return {"ok": False, "error": "Missing STRIPE_WEBHOOK_SECRET", "event_type": ""}
    try:
        stripe = _client()
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
        return {"ok": True, "event_type": event.get("type") or "", "event_id": event.get("id") or ""}
    except Exception as exc:
        return {"ok": False, "error": f"Webhook signature failed: {exc}", "event_type": ""}


def reconcile_recent_sessions(limit: int = 20) -> list[dict[str, Any]]:
    """Admin: pull recent Checkout Sessions and persist any newly paid ones."""
    out: list[dict[str, Any]] = []
    if not stripe_configured():
        return out
    try:
        stripe = _client()
        listed = stripe.checkout.Session.list(limit=max(1, min(int(limit), 50)))
        for session in listed.data or []:
            d = _session_to_dict(session)
            if session_is_paid(d):
                out.append(confirm_checkout_session(d["id"]))
            else:
                out.append(
                    {
                        "ok": True,
                        "paid": False,
                        "session_id": d["id"],
                        "error": f"payment_status={d.get('payment_status')}",
                    }
                )
    except Exception as exc:
        out.append({"ok": False, "paid": False, "session_id": "", "error": str(exc)})
    return out
