"""
Stripe EMD checkout — gate assignment PDFs behind a deposit.
"""

from __future__ import annotations

import os


def stripe_configured() -> bool:
    return bool((os.getenv("STRIPE_SECRET_KEY") or "").strip())


def stripe_mode() -> str:
    """Return 'live', 'test', or 'off'."""
    key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    if not key:
        return "off"
    if key.startswith("sk_live_"):
        return "live"
    if key.startswith("sk_test_"):
        return "test"
    return "unknown"


def create_checkout_session(
    *,
    address: str,
    assignment_fee: float,
    emd_cents: int | None = None,
    success_url: str | None = None,
    cancel_url: str | None = None,
) -> str | None:
    """
    Create a Stripe Checkout session for non-refundable EMD.
    Default EMD: $2,500 (250000 cents) or STRIPE_EMD_CENTS env.
    On failure returns None and sets create_checkout_session.last_error.
    """
    create_checkout_session.last_error = ""  # type: ignore[attr-defined]
    secret = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    if not secret:
        create_checkout_session.last_error = "Missing STRIPE_SECRET_KEY"  # type: ignore[attr-defined]
        return None

    import stripe

    stripe.api_key = secret
    amount = emd_cents
    if amount is None:
        amount = int(os.getenv("STRIPE_EMD_CENTS") or "250000")

    base = (os.getenv("APP_BASE_URL") or "http://localhost:8501").rstrip("/")
    success = success_url or f"{base}/?emd_paid=1"
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
            metadata={
                "address": address[:500],
                "assignment_fee": str(assignment_fee),
            },
        )
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


def emd_amount_dollars() -> float:
    return int(os.getenv("STRIPE_EMD_CENTS") or "250000") / 100.0
