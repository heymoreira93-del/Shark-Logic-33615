"""
Stripe EMD checkout — gate assignment PDFs behind a deposit.
"""

from __future__ import annotations

import os
from typing import Any


def stripe_configured() -> bool:
    return bool((os.getenv("STRIPE_SECRET_KEY") or "").strip())


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
    """
    secret = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    if not secret:
        return None

    import stripe

    stripe.api_key = secret
    amount = emd_cents
    if amount is None:
        amount = int(os.getenv("STRIPE_EMD_CENTS") or "250000")

    base = (os.getenv("APP_BASE_URL") or "http://localhost:8501").rstrip("/")
    success = success_url or f"{base}/?emd_paid=1"
    cancel = cancel_url or f"{base}/?emd_cancel=1"

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Deal Assignment EMD — {address[:80]}",
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


def emd_amount_dollars() -> float:
    return int(os.getenv("STRIPE_EMD_CENTS") or "250000") / 100.0
