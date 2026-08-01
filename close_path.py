"""
Path to fee — checklist + title opening packet helpers.
Does not contact title by itself; builds the packet / mailto so you or buyer can open the file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from db import list_deals


def _ensure_secrets() -> None:
    try:
        from secrets_bootstrap import bootstrap_secrets

        bootstrap_secrets()
    except Exception:
        pass


# Placeholder / demo assignee names — never treat as a live locked buyer.
_FAKE_BUYERS = frozenset(
    {
        "",
        "tbd",
        "tbd cash buyer",
        "cash buyer",
        "kingpin",
        "kingpin properties",
        "kingpin properties llc",
        "buyer",
        "assignee",
        "test buyer",
        "demo buyer",
    }
)


def is_live_assignee(name: str) -> bool:
    """True only when a real buyer entity was typed (not app defaults/placeholders)."""
    cleaned = " ".join((name or "").strip().lower().split())
    if cleaned in _FAKE_BUYERS:
        return False
    if "kingpin" in cleaned and "properties" in cleaned:
        # Legacy default baked into older UI — require explicit override elsewhere.
        return False
    return len(cleaned) >= 3


def find_signed_deal_for_address(address: str) -> dict[str, Any] | None:
    """Newest SIGNED deal whose address loosely matches."""
    needle = (address or "").strip().lower()
    if not needle:
        return None
    street = needle.split(",")[0].strip()
    for deal in list_deals(limit=200):
        if (deal.get("status") or "") != "SIGNED":
            continue
        hay = (deal.get("address") or "").strip().lower()
        if needle in hay or street and street in hay:
            return deal
    return None


def close_checklist(
    *,
    address: str,
    assignment_pdf: str = "",
    emd_paid: bool = False,
    title_file_number: str = "",
    assignee_name: str = "",
) -> list[dict[str, Any]]:
    """
    Ordered steps to collect the assignment fee.
    Each item: {id, label, done, how}
    """
    signed = find_signed_deal_for_address(address)
    assign_path = Path(assignment_pdf) if assignment_pdf else None
    assign_ok = bool(assign_path and assign_path.exists())
    file_no = (title_file_number or "").strip()
    buyer_ok = is_live_assignee(assignee_name)

    return [
        {
            "id": "seller_signed",
            "label": "Seller under contract (cash offer SIGNED)",
            "done": bool(signed),
            "how": (
                f"SIGNED by {signed.get('signature')} · deal `{signed.get('id')}`"
                if signed
                else "Calculator → Seller cell # → Generate PDF → Fire SMS → seller Accept & Sign"
            ),
        },
        {
            "id": "buyer_locked",
            "label": "Real cash buyer locked (not a placeholder name)",
            "done": buyer_ok,
            "how": (
                f"Assignee: {assignee_name.strip()}"
                if buyer_ok
                else "Enter the buyer's legal entity + confirm they agreed — "
                "KINGPIN/TBD defaults do NOT count"
            ),
        },
        {
            "id": "assignment_pdf",
            "label": "Live assignment PDF (real buyer on the face)",
            "done": assign_ok and buyer_ok,
            "how": (
                str(assign_path)
                if assign_ok and buyer_ok
                else "Lock a real buyer, then generate assignment (draft-only blocked for title)"
            ),
        },
        {
            "id": "emd",
            "label": "Buyer EMD collected (or wire unlock)",
            "done": bool(emd_paid) and buyer_ok,
            "how": "Buyer pays Stripe EMD / wire after they agree — Unlock PDF only after real commit",
        },
        {
            "id": "title_file",
            "label": "Title file opened (file number on record)",
            "done": bool(file_no) and buyer_ok,
            "how": "Send Title Packet only after seller SIGNED + real buyer locked",
        },
        {
            "id": "fee_at_close",
            "label": "Fee on settlement statement → paid at closing",
            "done": False,
            "how": "Confirm DealShark assignment fee on CD/HUD before funding",
        },
    ]


def title_company_email() -> str:
    _ensure_secrets()
    return (os.getenv("TITLE_COMPANY_EMAIL") or "").strip()


def title_company_name() -> str:
    _ensure_secrets()
    return (os.getenv("TITLE_COMPANY_NAME") or "Title / Escrow").strip()


def build_title_cover_email(
    *,
    address: str,
    assignor_name: str,
    assignee_name: str,
    assignment_fee: float,
    purchase_price: float,
    closing_date: str = "",
    seller_name: str = "",
    deal_id: str = "",
) -> dict[str, str]:
    """Subject + body to open an assignment / double-close file."""
    title = title_company_name()
    subject = f"Open file — Assignment / double close — {address}"
    body = (
        f"Hello {title},\n\n"
        f"Please open a file for an assignment / double closing on:\n\n"
        f"Property: {address}\n"
        f"Seller (on purchase agreement): {seller_name or '[see attached PSA]'}\n"
        f"Assignor: {assignor_name}\n"
        f"Assignee (cash buyer): {assignee_name}\n"
        f"Underlying purchase price: ${purchase_price:,.2f}\n"
        f"Assignment fee due to Assignor at closing: ${assignment_fee:,.2f}\n"
        f"Target closing: {closing_date or '[see contract]'}\n"
        f"Purchase agreement deal id: {deal_id or 'n/a'}\n\n"
        f"Attached / enclosed:\n"
        f"1) Fully executed (or seller-signed) Purchase Agreement\n"
        f"2) Assignment of PSA + Disbursement Authorization "
        f"(pay ${assignment_fee:,.2f} to {assignor_name} from buyer's side)\n\n"
        f"Please reply with the file number and confirm {assignor_name} is on the "
        f"settlement statement for the assignment fee.\n\n"
        f"Thank you,\n{assignor_name}\n"
    )
    return {"subject": subject, "body": body}


def title_mailto_link(subject: str, body: str, to_email: str = "") -> str:
    to = (to_email or title_company_email()).strip()
    return (
        f"mailto:{quote(to, safe='@+.')}"
        f"?subject={quote(subject)}&body={quote(body)}"
    )


def write_title_cover_txt(
    *,
    address: str,
    subject: str,
    body: str,
    output_dir: Path | None = None,
) -> Path:
    out = output_dir or (Path(__file__).resolve().parent / "contracts")
    out.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in address)[:60]
    path = out / f"Title_Packet_Cover_{safe or 'Property'}.txt"
    path.write_text(f"Subject: {subject}\n\n{body}", encoding="utf-8")
    return path
