"""
Assignment of Real Estate Purchase and Sale Agreement PDF.
Black-ink boilerplate + closing-agent instructions + disbursement page.
ASCII-only text for fpdf Helvetica compatibility.
"""

from __future__ import annotations

import datetime
import os
import re
from pathlib import Path
from typing import Any

from fpdf import FPDF

CONTRACTS_DIR = Path(__file__).resolve().parent / "contracts"


def _safe_name(address: str) -> str:
    cleaned = re.sub(r"[^\w\s\-]", "", address or "Property")
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned[:80] or "Property"


def _wire_info() -> dict[str, str]:
    return {
        "bank": (os.getenv("WIRE_BANK") or "Title Company Escrow - SEE CLOSING AGENT").strip(),
        "account": (os.getenv("WIRE_ACCOUNT") or "[PROVIDE AT CLOSING]").strip(),
        "routing": (os.getenv("WIRE_ROUTING") or "[PROVIDE AT CLOSING]").strip(),
        "title_company": (os.getenv("TITLE_COMPANY_NAME") or "Title Agent / Escrow Officer").strip(),
    }


def add_disbursement_page(
    pdf: FPDF,
    assignment_fee: float,
    your_name: str,
    address: str,
    wire_info: dict[str, Any] | None = None,
) -> None:
    """Title-company instruction page: pay Assignor fee from buyer proceeds."""
    info = wire_info or _wire_info()
    pdf.add_page()

    pdf.set_text_color(180, 0, 0)
    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(
        0,
        7,
        "ATTENTION CLOSING AGENT:\n"
        "Per the terms of this Assignment, the Assignment Fee is to be treated as a "
        "Contractual Obligation and paid directly to "
        f"{your_name} at closing. Do not net this fee against the seller's proceeds. "
        "This is a Buyer-paid assignment fee.",
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "DISBURSEMENT AUTHORIZATION", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", size=11)
    body = (
        f"TO: {info.get('title_company', 'TITLE AGENT / ESCROW OFFICER')}\n\n"
        f"This document serves as formal authorization to disburse funds from the "
        f"closing of the property located at:\n\n{address}\n\n"
        f"On the closing date, you are hereby directed to pay {your_name} the sum of "
        f"${assignment_fee:,.2f} as an Assignment Fee.\n\n"
        f"These funds are to be paid directly to the Assignor from the Buyer's "
        f"side of the settlement statement (HUD-1 / Closing Disclosure).\n\n"
        f"WIRE / ESCROW INSTRUCTIONS:\n"
        f"Bank: {info.get('bank', '')}\n"
        f"Account Name: {your_name}\n"
        f"Account Number: {info.get('account', '')}\n"
        f"Routing Number: {info.get('routing', '')}\n\n"
        f"Confirm final wire instructions with your title company before funding."
    )
    pdf.multi_cell(0, 6, body)
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0,
        5,
        "FOOTER DISCLAIMER: This is an Assignment of Equitable Interest / contractual "
        "rights under a purchase agreement - not a brokerage of real property. "
        "Operational template only. Have a Florida-licensed attorney and title company "
        "review before relying on it for a live closing.",
    )


def generate_assignment_pdf(
    address: str,
    buyer_name: str,
    assignment_fee: float,
    *,
    assignor_name: str = "DealShark Acquisitions",
    purchase_price: float | None = None,
    output_dir: Path | None = None,
    include_disbursement: bool = True,
    flood_insurance_required: bool = False,
    emd_amount: float = 2500.0,
    closing_date: str = "",
    emd_paid_via_stripe: bool = False,
    emd_paid_at: str = "",
) -> Path:
    """
    Build Assignment of Real Estate Purchase and Sale Agreement PDF.
    """
    out_dir = output_dir or CONTRACTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    date_str = datetime.date.today().strftime("%B %d, %Y")
    assignee = buyer_name.strip() or "TBD Cash Buyer"
    close_line = closing_date.strip() or "(closing date per Original Agreement)"
    price_bit = (
        f"Underlying Original Agreement purchase price: ${purchase_price:,.2f}.\n"
        if purchase_price is not None
        else ""
    )

    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(
        0,
        7,
        "ASSIGNMENT OF REAL ESTATE PURCHASE AND SALE AGREEMENT",
        align="C",
    )
    pdf.ln(4)

    if flood_insurance_required:
        pdf.set_text_color(180, 0, 0)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(
            0,
            6,
            "WARNING: FLOOD INSURANCE REQUIRED - High Risk Flood Zone (AE). "
            "MAO / offer includes a $15,000 flood-risk buffer. "
            "Assignee must verify NFIP/private premiums.",
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    pdf.set_font("Helvetica", size=10)
    boilerplate = (
        f"This Assignment of Real Estate Purchase and Sale Agreement "
        f'("Assignment") is made this {date_str} by and between '
        f'{assignor_name} ("Assignor") and {assignee} ("Assignee").\n\n'
        f"RECITALS\n"
        f"A. Assignor entered into a certain Real Estate Purchase and Sale Agreement "
        f'("Original Agreement") for the property located at {address} ("Property").\n'
        f"B. Assignor is not the owner of record but holds equitable interest via a "
        f"fully executed purchase agreement. Assignor desires to assign all its rights "
        f"and interests in the Original Agreement to Assignee, and Assignee desires to "
        f"assume such rights and interests.\n"
        f"{price_bit}\n"
        f"AGREEMENT\n"
        f"1. ASSIGNMENT: For the sum of ${assignment_fee:,.2f}, Assignor hereby assigns "
        f"all rights, title, and interest in the Original Agreement to Assignee.\n"
        f"2. EARNEST MONEY: Assignee has paid or shall pay a non-refundable Earnest Money "
        f"Deposit (EMD) of ${emd_amount:,.2f} via electronic transfer. This deposit shall "
        f"be credited to the total Assignment Fee at closing.\n"
        f'3. "AS-IS" CONDITION: Assignee acknowledges they are purchasing the contract '
        f'interest in "AS-IS" condition and has performed all necessary due diligence, '
        f"including flood and insurance review for Tampa Bay (including 33615).\n"
        f"4. DISBURSEMENT: Assignee hereby instructs the Title Company/Closing Agent to "
        f"disburse the balance of the Assignment Fee directly to Assignor from the "
        f"Buyer's side of the Settlement Statement at the time of closing.\n"
        f"5. INDEMNITY: Assignee shall indemnify and hold Assignor harmless from any and "
        f"all claims or liabilities arising from the Original Agreement after the date "
        f"of this Assignment.\n"
        f"6. VANISH / DEFAULT: If Assignee fails to close by {close_line}, the EMD is "
        f"forfeited to Assignor and this Assignment is null and void, restoring "
        f"Assignor's rights under the Original Agreement.\n"
        f"7. NATURE OF INTEREST: This instrument assigns equitable / contractual rights "
        f"under the Original Agreement. It is not a brokerage of real property and does "
        f"not convey record title until closing of the Original Agreement.\n"
    )
    pdf.multi_cell(0, 5, boilerplate)
    pdf.ln(4)

    if emd_paid_via_stripe:
        stamp = emd_paid_at or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(0, 120, 60)
        pdf.multi_cell(
            0,
            5,
            f"EMD PAID VIA STRIPE - Timestamp: {stamp} - "
            f"electronic payment confirmation evidences intent to be bound.",
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    pdf.set_font("Helvetica", size=10)
    pdf.cell(95, 8, "_______________________________", new_x="RIGHT")
    pdf.cell(0, 8, "_______________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 6, "Assignor Signature", new_x="RIGHT")
    pdf.cell(0, 6, "Assignee Signature", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.cell(95, 8, "_______________________________", new_x="RIGHT")
    pdf.cell(0, 8, "_______________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 6, "Date", new_x="RIGHT")
    pdf.cell(0, 6, "Date / EMD Stripe confirmation", new_x="LMARGIN", new_y="NEXT")

    wire = _wire_info()
    pdf.ln(10)
    pdf.set_text_color(180, 0, 0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(
        0,
        5,
        (
            f"TITLE / ESCROW WIRE (Assignment Fee at closing):\n"
            f"Bank: {wire['bank']} | Routing: {wire['routing']} | "
            f"Acct: {wire['account']} | Pay to: {assignor_name}"
        ),
    )
    pdf.set_text_color(0, 0, 0)

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0,
        4,
        "FOOTER: Assignment of Equitable Interest template. Not legal advice. "
        "Consult a Florida-licensed attorney and a Hillsborough title company "
        "(e.g. Sunbelt Title / Bay Title) that handles assignments or double closings "
        "before using on a live file.",
    )

    if include_disbursement:
        add_disbursement_page(pdf, assignment_fee, assignor_name, address, wire)

    file_name = f"Assignment_{_safe_name(address)}.pdf"
    path = out_dir / file_name
    pdf.output(str(path))
    return path
