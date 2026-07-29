"""
Contract Engine — DealShark Acquisitions offer PDF (fpdf2).
Sections: Purchase Price | Scope of Work | Market Analysis | Signature
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF


DEFAULT_INSPECTION_DAYS = 7
DEFAULT_BUYER = "Buyer LLC"
CONTRACTS_DIR = Path(__file__).resolve().parent / "contracts"


@dataclass
class ContractParties:
    seller_name: str
    buyer_name: str
    property_address: str
    purchase_price: float
    earnest_money: float
    closing_date: date
    inspection_days: int = DEFAULT_INSPECTION_DAYS
    expiration_date: date | None = None
    expiration_time: str = "9:00 PM"
    scope_lines: list[dict[str, Any]] = field(default_factory=list)
    comps: list[dict[str, Any]] = field(default_factory=list)
    rehab_total: float = 0.0
    arv: float = 0.0


def balance_due(purchase_price: float, earnest_money: float) -> float:
    return purchase_price - earnest_money


def _street_slug(address: str) -> str:
    cleaned = re.sub(r"[^\w\s\-]", "", address)
    cleaned = re.sub(r"\s+", "", cleaned.strip())
    return cleaned.upper()[:80] or "PROPERTY"


def _money(amount: float) -> str:
    return f"${amount:,.2f}"


def _parse_closing(value: date | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


class DealSharkPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, "DEALSHARK ACQUISITIONS", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 6, "Cash Offer / Purchase Memorandum", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.cell(
            0,
            8,
            "Simplified template - consult a licensed attorney in your state before use.",
            align="C",
        )


def build_pdf(parties: ContractParties) -> FPDF:
    bal = balance_due(parties.purchase_price, parties.earnest_money)
    exp_date = parties.expiration_date or date.today()
    exp_time = parties.expiration_time or "9:00 PM"
    closing = (
        parties.closing_date.isoformat()
        if isinstance(parties.closing_date, date)
        else str(parties.closing_date)
    )

    pdf = DealSharkPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    pdf.set_font("Helvetica", "B", 10)
    pdf.write(5, "PARTIES: ")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        0,
        5,
        f"Buyer {parties.buyer_name} offers to purchase from Seller {parties.seller_name} "
        f"the property at {parties.property_address}.",
    )
    pdf.ln(2)

    # Section 1 — Purchase Price
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "SECTION 1 - PURCHASE PRICE", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        0,
        5,
        f"Purchase Price: {_money(parties.purchase_price)}\n"
        f"Earnest Money Deposit: {_money(parties.earnest_money)} (held by escrow/title)\n"
        f"Balance at Closing: {_money(bal)}\n"
        f"Closing on or before: {closing}\n"
        f"Inspection Period: {parties.inspection_days} days from effective date "
        f"(Buyer may cancel for any reason with full EMD refund).\n"
        f"Offer expires: {exp_time} on {exp_date.isoformat()}",
    )
    pdf.ln(2)

    # Section 2 — Scope of Work
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "SECTION 2 - SCOPE OF WORK", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    if parties.scope_lines:
        for line in parties.scope_lines:
            pdf.cell(
                0,
                5,
                f"- {line['item']}: {line['detail']} = {_money(line['cost'])}",
                new_x="LMARGIN",
                new_y="NEXT",
            )
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, f"Estimated Rehab Total: {_money(parties.rehab_total)}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
    else:
        pdf.multi_cell(0, 5, "No itemized repairs selected. Buyer to confirm condition during inspection.")
    pdf.ln(2)

    # Section 3 — Market Analysis (comps)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "SECTION 3 - MARKET ANALYSIS (COMPS)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    if parties.arv:
        pdf.cell(0, 5, f"Subject ARV reference: {_money(parties.arv)}", new_x="LMARGIN", new_y="NEXT")
    if parties.comps:
        for c in parties.comps:
            pdf.set_x(pdf.l_margin)
            line = (
                f"- {c['status']}: {c['address']} | {_money(c['sold_price'])} | "
                f"{c.get('distance', '')} | {c.get('beds', '?')}bd/{c.get('baths', '?')}ba | "
                f"{c.get('sqft', '?')} sqft"
            )
            pdf.multi_cell(pdf.epw, 5, line)
            pdf.ln(1)
    else:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, 5, "Comps unavailable at generation time.")
    pdf.ln(2)

    # Assignment
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        pdf.epw,
        5,
        "ASSIGNMENT: Buyer may assign this contract to any third party without Seller's "
        "additional consent.",
    )
    pdf.ln(2)

    # Section 4 — Signature
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "SECTION 4 - SIGNATURE", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        0,
        5,
        "By signing below (or via electronic signature on the DealShark acceptance page), "
        "Seller accepts the Purchase Price and terms herein.",
    )
    pdf.ln(6)
    pdf.cell(95, 6, "Seller: _______________________________", new_x="RIGHT")
    pdf.cell(0, 6, "Date: ______________", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.cell(95, 6, "Buyer: _______________________________", new_x="RIGHT")
    pdf.cell(0, 6, "Date: ______________", new_x="LMARGIN", new_y="NEXT")

    return pdf


def generate_contract(
    address: str | None = None,
    seller: str | None = None,
    price: float | None = None,
    emd: float | None = None,
    closing_date: date | str | None = None,
    buyer: str = DEFAULT_BUYER,
    inspection_days: int = DEFAULT_INSPECTION_DAYS,
    expiration_date: date | None = None,
    expiration_time: str = "9:00 PM",
    parties: ContractParties | None = None,
    scope_lines: list[dict[str, Any]] | None = None,
    comps: list[dict[str, Any]] | None = None,
    rehab_total: float = 0.0,
    arv: float = 0.0,
    output_dir: Path | None = None,
) -> Path:
    """Build DealShark PDF and save as STREETADDRESS_OFFER.pdf."""
    if parties is None:
        if not address or seller is None or price is None or emd is None or closing_date is None:
            raise ValueError(
                "Provide parties=... or address, seller, price, emd, and closing_date"
            )
        parties = ContractParties(
            seller_name=seller,
            buyer_name=buyer,
            property_address=address,
            purchase_price=float(price),
            earnest_money=float(emd),
            closing_date=_parse_closing(closing_date),
            inspection_days=inspection_days,
            expiration_date=expiration_date or date.today(),
            expiration_time=expiration_time,
            scope_lines=scope_lines or [],
            comps=comps or [],
            rehab_total=rehab_total,
            arv=arv,
        )
    else:
        if parties.expiration_date is None:
            parties.expiration_date = date.today()
        if scope_lines is not None:
            parties.scope_lines = scope_lines
        if comps is not None:
            parties.comps = comps
        if rehab_total:
            parties.rehab_total = rehab_total
        if arv:
            parties.arv = arv

    out_dir = output_dir or CONTRACTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_street_slug(parties.property_address)}_OFFER.pdf"
    path = out_dir / filename
    pdf = build_pdf(parties)
    pdf.output(str(path))
    return path


def print_success(path: Path, parties: ContractParties) -> None:
    bal = balance_due(parties.purchase_price, parties.earnest_money)
    print("\n=== Contract Generated ===")
    print(f"File:            {path}")
    print(f"Property:        {parties.property_address}")
    print(f"Purchase Price:  {_money(parties.purchase_price)}")
    print(f"Earnest Money:   {_money(parties.earnest_money)}")
    print(f"Balance Due:     {_money(bal)}")
    print(f"Closing Date:    {parties.closing_date.isoformat()}")
    print("==========================\n")
