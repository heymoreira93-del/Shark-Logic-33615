"""
DealShark Property Research Package — investor PDF from War Room lead data.

Uses stored lead fields + optional live RentCast property/comps when available.
Does NOT invent phones, equity, vacancy, distress, or sale prices. No auto-contact.
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

REPORTS_DIR = Path(__file__).resolve().parent / "contracts" / "investor_reports"
PACKAGE_PRICE_LABEL = "$250 DealShark Property Research Package"
DEFAULT_MARKET_FACTOR = 0.70
DEFAULT_CLOSING_PCT = 0.03


def _ascii(text: str) -> str:
    raw = (text or "").replace("\u2014", "-").replace("\u2013", "-").replace("\u2019", "'")
    return raw.encode("latin-1", "replace").decode("latin-1")


def _money(val: Any) -> str:
    try:
        n = float(val or 0)
    except (TypeError, ValueError):
        return "N/A"
    if n == 0:
        return "Not available"
    return f"${n:,.0f}"


def _num_or_na(val: Any, suffix: str = "", *, thousands: bool = True) -> str:
    if val in (None, "", "?", "Unknown"):
        return "Not available"
    try:
        n = float(val)
        if n == 0:
            return "Not available"
        if n == int(n):
            iv = int(n)
            return f"{iv:,}{suffix}" if thousands else f"{iv}{suffix}"
        return f"{n:g}{suffix}"
    except (TypeError, ValueError):
        return str(val)


def _street_slug(address: str) -> str:
    cleaned = re.sub(r"[^\w\s\-]", "", address or "")
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return (cleaned.upper()[:60] or "PROPERTY")


def _as_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def lead_data_availability(lead: dict[str, Any], subject: dict[str, Any] | None = None) -> dict[str, str]:
    """Map field -> available | estimate | missing | unverified_flag for reporting."""

    def has_num(k: str) -> bool:
        return _as_float(lead.get(k)) > 0

    subject = subject or {}
    return {
        "address": "available" if (lead.get("address") or "").strip() else "missing",
        "owner_name": "available" if (lead.get("seller_name") or "").strip() else "missing",
        "mailing_address": "available" if (lead.get("mailing_address") or "").strip() else "missing",
        "sqft": "available" if _as_float(subject.get("sqft")) > 0 else "missing",
        "beds_baths": (
            "available"
            if subject.get("bedrooms") not in (None, "") and subject.get("bathrooms") not in (None, "")
            else "missing"
        ),
        "year_built": "available" if subject.get("yearBuilt") not in (None, "") else "missing",
        "lot_size": "available" if _as_float(subject.get("lotSizeSqft")) > 0 else "missing",
        "arv": "estimate" if has_num("arv") else "missing",
        "mao": "estimate" if has_num("mao") else "missing",
        "wholesale_fee": "estimate" if has_num("wholesale_fee") else "missing",
        "estimated_equity": "estimate" if has_num("estimated_equity") else "missing",
        "last_sale_price": "available" if has_num("last_sale_price") else "missing",
        "repairs_estimate": "estimate" if has_num("repairs_estimate") else "missing",
        "seller_phone": "available" if (lead.get("seller_phone") or "").strip() else "missing",
        "risk_level": "available" if (lead.get("risk_level") or "").strip() else "missing",
        "flood_risk": "unverified_flag",
        "vacant": "unverified_flag",
        "absentee": "unverified_flag",
        "foreclosure_case": (
            "available" if (lead.get("foreclosure_case") or "").strip() else "missing"
        ),
    }


def _fetch_subject_property(address: str) -> dict[str, Any]:
    """Live RentCast subject characteristics. Never invent values."""
    try:
        from data_engine import get_property_data

        prop = get_property_data(address or "")
        if not prop:
            err = getattr(get_property_data, "last_error", "") or "not found"
            return {"source": "none", "error": err}
        return {
            "sqft": _as_float(prop.get("squareFootage")),
            "bedrooms": prop.get("bedrooms"),
            "bathrooms": prop.get("bathrooms"),
            "yearBuilt": prop.get("yearBuilt"),
            "propertyType": prop.get("propertyType") or "",
            "lotSizeSqft": _as_float(prop.get("lotSizeSqft")),
            "lastSalePrice": _as_float(prop.get("lastSalePrice")),
            "zipCode": prop.get("zipCode") or "",
            "taxAssessedValue": _as_float(prop.get("taxAssessedValue")),
            "taxAssessedYear": prop.get("taxAssessedYear") or "",
            "subdivision": prop.get("subdivision") or "",
            "source": prop.get("source") or "rentcast",
            "error": "",
        }
    except Exception as exc:
        return {"source": "none", "error": str(exc)}


HEURISTIC_PPS = 180.0  # seller_factory fallback when last sale missing


def explain_stored_arv_basis(stored_arv: float, subject_sqft: float) -> str:
    """Label how the stored DealShark ARV was likely derived — never invent a new number."""
    if stored_arv <= 0:
        return "Stored ARV missing."
    if subject_sqft > 0:
        heuristic = subject_sqft * HEURISTIC_PPS
        if abs(stored_arv - heuristic) < 1.0:
            return (
                f"Stored ARV equals living area x ${HEURISTIC_PPS:.0f}/sf heuristic "
                f"({subject_sqft:,.0f} x {HEURISTIC_PPS:.0f} = {_money(heuristic)}). "
                "This is NOT a sold-comps appraisal; it is DealShark's no-last-sale fallback."
            )
        implied_pps = stored_arv / subject_sqft
        return (
            f"Stored ARV implies ~${implied_pps:,.0f}/sf on {subject_sqft:,.0f} sqft. "
            "Confirm basis in DealShark inputs (comps, last sale, or manual entry)."
        )
    return "Stored ARV present but subject sqft unavailable — basis not recomputed."


def classify_comp_quality(
    comp: dict[str, Any],
    *,
    subject_sqft: float,
    subject_year: int | None,
    subject_baths: float | None,
    subject_zip: str,
) -> dict[str, Any]:
    """
    Score whether a sold comp is a fair match. Adjustments are qualitative $/sf haircuts,
    not a claim of true market value. Condition/reno are UNKNOWN unless separately verified.
    """
    price = _as_float(comp.get("sold_price"))
    sqft = _as_float(comp.get("sqft"))
    pps = (price / sqft) if sqft > 0 else 0.0
    year_raw = comp.get("yearBuilt")
    try:
        year = int(float(year_raw)) if year_raw not in (None, "", "?") else None
    except (TypeError, ValueError):
        year = None
    try:
        baths = float(comp.get("baths")) if comp.get("baths") not in (None, "", "?") else None
    except (TypeError, ValueError):
        baths = None
    zip_c = ""
    addr = str(comp.get("address") or "")
    m = re.search(r"\b(33\d{3})\b", addr)
    if m:
        zip_c = m.group(1)

    notes: list[str] = []
    adj = 0.0  # applied to $/sf; negative = comp superior to subject
    tier = "core"

    if subject_sqft > 0 and sqft > 0:
        ratio = sqft / subject_sqft
        if ratio > 1.15:
            notes.append(f"larger (+{(ratio - 1) * 100:.0f}% sf)")
            adj -= 8
        elif ratio < 0.85:
            notes.append(f"smaller ({(1 - ratio) * 100:.0f}% less sf)")
            adj += 5

    if subject_year and year:
        dy = year - subject_year
        if dy >= 15:
            notes.append(f"newer (+{dy}y)")
            adj -= 15
            tier = "superior"
        elif dy <= -20:
            notes.append(f"older ({-dy}y)")
            adj += 8

    if subject_baths is not None and baths is not None and baths > subject_baths + 0.4:
        notes.append(f"more baths ({baths:g} vs {subject_baths:g})")
        adj -= 10
        tier = "superior"

    if year and year >= 2000:
        tier = "superior"

    if zip_c == "33618":
        notes.append("33618 (often stronger retail than 33612)")
        adj -= 12
    elif zip_c == "33613":
        notes.append("33613 adjacent")
        adj -= 3
    elif zip_c and subject_zip and zip_c == subject_zip:
        notes.append("same zip")
    elif zip_c:
        notes.append(f"zip {zip_c}")

    notes.append("condition/reno UNKNOWN")
    if subject_sqft > 0 and sqft > subject_sqft * 1.25:
        tier = "superior"

    return {
        "tier": tier,
        "pps": round(pps, 2),
        "adj_pps": round(max(pps + adj, 50.0), 2),
        "adj": adj,
        "notes": notes,
        "year": year,
        "zip": zip_c,
        "baths": baths,
    }


def reconcile_valuation(
    *,
    stored_arv: float,
    subject: dict[str, Any],
    comps: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Reconcile stored ARV vs filtered-comp implication.
    Does NOT auto-select the higher number.
    """
    sqft = _as_float(subject.get("sqft"))
    try:
        subject_year = int(float(subject.get("yearBuilt"))) if subject.get("yearBuilt") not in (None, "") else None
    except (TypeError, ValueError):
        subject_year = None
    try:
        subject_baths = float(subject.get("bathrooms")) if subject.get("bathrooms") not in (None, "") else None
    except (TypeError, ValueError):
        subject_baths = None
    subject_zip = str(subject.get("zipCode") or "")
    assess = _as_float(subject.get("taxAssessedValue"))
    assess_year = str(subject.get("taxAssessedYear") or "")

    annotated: list[dict[str, Any]] = []
    for c in comps:
        meta = classify_comp_quality(
            c,
            subject_sqft=sqft,
            subject_year=subject_year,
            subject_baths=subject_baths,
            subject_zip=subject_zip,
        )
        row = dict(c)
        row.update(meta)
        annotated.append(row)

    all_pps = [_as_float(c.get("pps")) for c in annotated if _as_float(c.get("pps")) > 0]
    core = [c for c in annotated if c.get("tier") == "core"]
    core_pps = [_as_float(c.get("pps")) for c in core if _as_float(c.get("pps")) > 0]
    core_adj = [_as_float(c.get("adj_pps")) for c in core if _as_float(c.get("adj_pps")) > 0]

    def _avg(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    def _med(vals: list[float]) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        return s[len(s) // 2]

    naive_avg_pps = _avg(all_pps)
    naive_arv = naive_avg_pps * sqft if sqft and naive_avg_pps else 0.0
    core_med_pps = _med(core_pps)
    core_arv = core_med_pps * sqft if sqft and core_med_pps else 0.0
    adj_med_pps = _med(core_adj)
    adj_arv = adj_med_pps * sqft if sqft and adj_med_pps else 0.0

    # Most defensible: do not adopt naive filtered average when superior comps inflate it
    # and/or when tax assessment + heuristic agree near the stored figure.
    heuristic = sqft * HEURISTIC_PPS if sqft else 0.0
    heuristic_match = abs(stored_arv - heuristic) < 1.0 if heuristic else False
    assess_supports_stored = assess > 0 and stored_arv > 0 and abs(assess - stored_arv) / stored_arv < 0.08

    if assess_supports_stored or heuristic_match:
        defensible = stored_arv
        rationale = (
            "Keep stored ARV as the preliminary package figure. "
            "It matches the no-last-sale $/sf heuristic and/or sits near the latest tax assessment. "
            "Higher filtered-comp averages are inflated by superior (newer / more baths / stronger-zip) sales "
            "and cannot be adopted without verified condition/renovation evidence."
        )
    elif core_arv > 0:
        # No assessment anchor: use core median, not naive high
        defensible = round(core_arv, 0)
        rationale = (
            "Stored ARV lacks assessment/heuristic support; using median of CORE comps only "
            "(superior comps excluded). Still preliminary — condition unknown."
        )
    else:
        defensible = stored_arv
        rationale = "Insufficient quality comps; retain stored ARV and flag high uncertainty."

    upside = round(adj_arv, 0) if adj_arv > defensible * 1.05 else 0.0
    return {
        "annotated_comps": annotated,
        "naive_filtered_arv": round(naive_arv, 0),
        "naive_avg_pps": round(naive_avg_pps, 2),
        "core_median_arv": round(core_arv, 0),
        "core_adj_arv": round(adj_arv, 0),
        "tax_assessed": assess,
        "tax_assessed_year": assess_year,
        "heuristic_arv": round(heuristic, 0),
        "heuristic_match": heuristic_match,
        "assess_supports_stored": assess_supports_stored,
        "defensible_arv": round(defensible, 0),
        "upside_if_condition_supports": upside,
        "rationale": rationale,
        "basis_note": explain_stored_arv_basis(stored_arv, sqft),
    }


def filter_comps_for_underwriting(
    comps: list[dict[str, Any]],
    *,
    subject_sqft: float = 0.0,
    subject_arv: float = 0.0,
    subject_type: str = "",
    max_keep: int = 6,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Keep comps that can support underwriting. Drop missing-spec and outlier sales.
    Does not invent replacements.
    """
    kept: list[dict[str, Any]] = []
    rejected_notes: list[str] = []
    subj_type = (subject_type or "").strip().lower()

    for c in comps:
        addr = (c.get("address") or "Comp").strip()
        price = _as_float(c.get("sold_price"))
        sqft = _as_float(c.get("sqft"))
        reasons: list[str] = []

        if price <= 0:
            reasons.append("no sale price")
        if sqft <= 0:
            reasons.append("missing sqft")
        beds = c.get("beds")
        baths = c.get("baths")
        if beds in (None, "", "?"):
            reasons.append("missing beds")
        if baths in (None, "", "?"):
            reasons.append("missing baths")

        if subject_sqft > 0 and sqft > 0:
            ratio = sqft / subject_sqft
            if ratio < 0.65 or ratio > 1.40:
                reasons.append(f"size mismatch ({int(sqft)} vs subject {int(subject_sqft)} sf)")

        if subject_arv > 0 and price > 0:
            if price > subject_arv * 2.25:
                reasons.append(f"sale ${_as_float(price):,.0f} >> subject ARV")
            elif price < subject_arv * 0.40:
                reasons.append(f"sale ${_as_float(price):,.0f} << subject ARV")

        ctype = (c.get("propertyType") or "").strip().lower()
        if subj_type and ctype and subj_type not in ctype and ctype not in subj_type:
            # Soft preference: only reject clear commercial/multi vs SFR mismatches
            commercialish = any(x in ctype for x in ("commercial", "land", "multi", "apartment"))
            subject_sfr = any(x in subj_type for x in ("single", "sfr", "residential", "house"))
            if commercialish and subject_sfr:
                reasons.append(f"type mismatch ({c.get('propertyType')})")

        if reasons:
            rejected_notes.append(f"{addr}: " + "; ".join(reasons))
            continue

        pps = price / sqft if sqft else 0.0
        row = dict(c)
        row["price_per_sqft"] = pps
        kept.append(row)

    # Drop $/sf outliers relative to median of remaining set
    if len(kept) >= 3:
        pps_vals = sorted(_as_float(c.get("price_per_sqft")) for c in kept)
        median = pps_vals[len(pps_vals) // 2]
        refined: list[dict[str, Any]] = []
        for c in kept:
            pps = _as_float(c.get("price_per_sqft"))
            if median > 0 and (pps < median * 0.55 or pps > median * 1.55):
                rejected_notes.append(
                    f"{c.get('address')}: $/sf outlier (${pps:,.0f} vs median ${median:,.0f})"
                )
                continue
            refined.append(c)
        kept = refined

    # Prefer closer / more recent when truncating
    def sort_key(c: dict[str, Any]) -> tuple[float, str]:
        return (_as_float(c.get("distance_miles")), str(c.get("sale_date") or ""))

    kept = sorted(kept, key=sort_key)[:max_keep]
    return kept, rejected_notes


def _fetch_comps(
    address: str,
    *,
    subject_sqft: float = 0.0,
    subject_arv: float = 0.0,
    subject_type: str = "",
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Best-effort comps with underwriting filters. Never fabricates rows."""
    try:
        from data_engine import get_tampa_comps

        raw = get_tampa_comps(address or "", radius_miles=2.0, limit=25) or []
        if len(raw) < 8:
            more = get_tampa_comps(address or "", radius_miles=3.0, limit=25) or []
            seen = {c.get("address") for c in raw}
            for c in more:
                if c.get("address") not in seen:
                    raw.append(c)
        if not raw:
            err = getattr(get_tampa_comps, "last_error", "") or ""
            note = "No sold comps returned for this address"
            if err:
                note += f" ({err})"
            return [], note, []
        kept, rejected = filter_comps_for_underwriting(
            raw,
            subject_sqft=subject_sqft,
            subject_arv=subject_arv,
            subject_type=subject_type,
        )
        note = (
            f"RentCast sold comps pulled {datetime.now().strftime('%Y-%m-%d %H:%M')}; "
            f"{len(kept)} kept after underwriting filters ({len(raw)} raw)."
        )
        return kept, note, rejected
    except Exception as exc:
        return [], f"Comps unavailable: {exc}", []


def explain_mao(
    arv: float,
    repairs: float,
    fee: float,
    stored_mao: float,
    *,
    zip_code: str = "",
) -> dict[str, Any]:
    """Document DealShark MAO formula used by shark_mao (70% rule + closing + zip buffers)."""
    closing = arv * DEFAULT_CLOSING_PCT
    flood_buffer = 0.0
    flood_note = ""
    try:
        from rehab import tampa_hazard_check

        hazard = tampa_hazard_check(str(zip_code or ""))
        flood_buffer = float(hazard.get("buffer_deduction") or 0)
        if flood_buffer > 0:
            flood_note = str(hazard.get("warning") or hazard.get("risk_level") or "flood buffer")
    except Exception:
        flood_buffer = 0.0
    computed = (arv * DEFAULT_MARKET_FACTOR) - repairs - fee - closing - flood_buffer
    return {
        "formula": (
            "MAO = (ARV x 70%) - repairs - assignment fee - closing allowance - zip risk buffer. "
            "Closing allowance = 3% of ARV (not 3% of MAO or purchase price)."
        ),
        "arv": arv,
        "market_factor": DEFAULT_MARKET_FACTOR,
        "repairs": repairs,
        "fee": fee,
        "closing": closing,
        "flood_buffer": flood_buffer,
        "flood_note": flood_note,
        "computed_mao": round(computed, 2),
        "stored_mao": round(stored_mao, 2),
        "matches_stored": abs(computed - stored_mao) < 2.0,
    }


def explain_arv_from_comps(
    subject_sqft: float,
    comps: list[dict[str, Any]],
    stored_arv: float,
) -> dict[str, Any]:
    pps_vals = [_as_float(c.get("price_per_sqft")) for c in comps if _as_float(c.get("price_per_sqft")) > 0]
    if not pps_vals or subject_sqft <= 0:
        return {
            "method": "insufficient filtered comps or subject sqft",
            "avg_pps": 0.0,
            "implied_arv": 0.0,
            "stored_arv": stored_arv,
        }
    avg_pps = sum(pps_vals) / len(pps_vals)
    implied = avg_pps * subject_sqft
    return {
        "method": "avg filtered-comp $/sf x subject sqft",
        "avg_pps": round(avg_pps, 2),
        "comp_count": len(pps_vals),
        "implied_arv": round(implied, 2),
        "stored_arv": stored_arv,
    }


class InvestorReportPDF(FPDF):
    def __init__(self, *, show_package_price: bool = False) -> None:
        super().__init__()
        self._show_package_price = show_package_price

    def header(self) -> None:
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 7, "DEALSHARK TAMPA", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 10)
        self.cell(
            0,
            6,
            "Property Research Report",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Helvetica", "I", 8)
        label = (
            PACKAGE_PRICE_LABEL
            if self._show_package_price
            else "Preliminary research only - not an appraisal or contracted deal"
        )
        self.cell(0, 5, _ascii(label), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7)
        self.multi_cell(
            0,
            3.5,
            "Estimates only. Not an appraisal, offer, or solicitation. "
            "Verify title, liens, taxes, occupancy, and condition independently. "
            "DealShark does not guarantee equity, ARV, vacancy, or contactability.",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )


def _section(pdf: FPDF, title: str) -> None:
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _ascii(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)


def _line(pdf: FPDF, label: str, value: str) -> None:
    pdf.set_font("Helvetica", size=9)
    pdf.multi_cell(0, 5, _ascii(f"{label} {value}"), new_x="LMARGIN", new_y="NEXT")


def _flag_line(pdf: FPDF, label: str, value: str, *, verified: bool) -> None:
    tag = "verified/on-file" if verified else "database flag - not independently verified"
    _line(pdf, f"{label}", f"{value}  [{tag}]")


def build_package_cover_pdf(leads: list[dict[str, Any]]) -> FPDF:
    """Sales cover sheet only — pricing lives here, not on every property page."""
    pdf = InvestorReportPDF(show_package_price=True)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    _section(pdf, "DealShark Tampa Research Package")
    pdf.multi_cell(
        0,
        5,
        _ascii(
            f"Product: {PACKAGE_PRICE_LABEL}. "
            "This package is preliminary screening research for investor review. "
            "It is not a contracted deal, not skip-traced contact data, and not legal advice."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    _section(pdf, "What is included")
    for item in (
        "Individual property research PDFs for the listed Tampa addresses",
        "Owner-of-record / mailing fields as stored in DealShark (when available)",
        "Subject property characteristics from RentCast when lookup succeeds",
        "Filtered sold comps (size/type/price screens applied)",
        "ARV and MAO calculation notes with explicit estimate labels",
        "Risk/motivation flags clearly marked as unverified database indicators unless on file",
    ):
        _line(pdf, "-", item)
    _section(pdf, "What is NOT included / not claimed")
    for item in (
        "Verified seller motivation or confirmed vacant status",
        "Seller phone numbers (unless separately funded skip-trace)",
        "Guaranteed equity, title clearance, or appraisal-grade ARV",
        "Properties under contract or available for assignment",
    ):
        _line(pdf, "-", item)
    _section(pdf, "Properties in this pack")
    for lead in leads:
        _line(
            pdf,
            f"#{lead.get('id')}:",
            f"{(lead.get('address') or 'Address n/a')} | stored ARV {_money(lead.get('arv'))}",
        )
    _section(pdf, "Invoice / delivery")
    pdf.multi_cell(
        0,
        5,
        _ascii(
            "Invoice via MLTX Pro LLC after buyer confirmation. "
            "Deliverable is the research ZIP of PDFs only. "
            "Investors must independently verify before underwriting or outreach."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return pdf


def build_investor_report_pdf(
    lead: dict[str, Any],
    *,
    include_live_comps: bool = True,
) -> FPDF:
    addr = (lead.get("address") or "").strip() or "Address not on file"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    subject = _fetch_subject_property(addr) if addr and addr != "Address not on file" else {}
    avail = lead_data_availability(lead, subject)

    arv = _as_float(lead.get("arv"))
    mao = _as_float(lead.get("mao"))
    fee = _as_float(lead.get("wholesale_fee")) or 10000.0
    repairs = _as_float(lead.get("repairs_estimate"))
    equity = _as_float(lead.get("estimated_equity"))
    last_sale = _as_float(lead.get("last_sale_price"))
    if last_sale <= 0:
        last_sale = _as_float(subject.get("lastSalePrice"))

    comps: list[dict[str, Any]] = []
    comps_note = "Comps not requested"
    rejected: list[str] = []
    if include_live_comps and addr and addr != "Address not on file":
        comps, comps_note, rejected = _fetch_comps(
            addr,
            subject_sqft=_as_float(subject.get("sqft")),
            subject_arv=arv,
            subject_type=str(subject.get("propertyType") or ""),
        )

    recon = reconcile_valuation(stored_arv=arv, subject=subject, comps=comps)
    defensible_arv = _as_float(recon.get("defensible_arv")) or arv
    zip_for_mao = str(lead.get("zip_code") or subject.get("zipCode") or "")
    mao_defensible = explain_mao(
        defensible_arv, repairs, fee, mao, zip_code=zip_for_mao
    )

    pdf = InvestorReportPDF(show_package_price=False)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    _section(pdf, "1. Property snapshot")
    _line(pdf, "Address:", addr)
    _line(pdf, "Zip:", str(lead.get("zip_code") or subject.get("zipCode") or "Not available"))
    _line(pdf, "Subdivision:", str(subject.get("subdivision") or "Not available"))
    _line(pdf, "Report generated:", generated)
    _line(pdf, "Lead status:", str(lead.get("status") or "Not Contacted"))
    _line(pdf, "War Room ID:", f"#{lead.get('id')}")

    _section(pdf, "2. Subject property characteristics")
    src = subject.get("source") or "none"
    if subject.get("error") and src == "none":
        _line(pdf, "Lookup:", f"Not available ({subject.get('error')})")
    else:
        _line(pdf, "Source:", f"RentCast ({src})" if src != "none" else "Not available")
    _line(pdf, "Property type:", str(subject.get("propertyType") or "Not available"))
    _line(pdf, "Living area:", _num_or_na(subject.get("sqft"), " sqft"))
    _line(pdf, "Bedrooms:", _num_or_na(subject.get("bedrooms")))
    _line(pdf, "Bathrooms:", _num_or_na(subject.get("bathrooms")))
    _line(pdf, "Year built:", _num_or_na(subject.get("yearBuilt"), thousands=False))
    _line(pdf, "Lot size:", _num_or_na(subject.get("lotSizeSqft"), " sqft"))
    if _as_float(subject.get("taxAssessedValue")) > 0:
        _line(
            pdf,
            "Latest tax assessment:",
            f"{_money(subject.get('taxAssessedValue'))} ({subject.get('taxAssessedYear') or 'year n/a'})",
        )
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0,
        4,
        _ascii(
            "Characteristics are shown only when returned by the property lookup. "
            "Missing fields are not invented. Condition / renovation quality is NOT inspected."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    _section(pdf, "3. Public ownership (as stored)")
    owner = (lead.get("seller_name") or "").strip()
    _line(pdf, "Owner of record:", owner or "Not available in DealShark")
    _line(
        pdf,
        "Mailing address:",
        (lead.get("mailing_address") or "").strip() or "Not available",
    )
    _flag_line(
        pdf,
        "Owner-occupied:",
        "Unknown" if lead.get("owner_occupied") in (None, "", -1) else ("Yes" if lead.get("owner_occupied") else "No"),
        verified=False,
    )
    _flag_line(
        pdf,
        "Absentee:",
        "Yes" if lead.get("absentee") else ("No" if lead.get("absentee") == 0 else "Unknown"),
        verified=False,
    )
    _flag_line(
        pdf,
        "Vacant proxy:",
        "Yes" if lead.get("vacant") else ("No" if lead.get("vacant") == 0 else "Unknown"),
        verified=False,
    )
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0,
        4,
        _ascii(
            "Vacant/absentee values are DealShark database proxies (often mailing != subject), "
            "not a verified field inspection or utility confirmation."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    _line(
        pdf,
        "Phone:",
        "Not included in this package (requires funded skip-trace or manual research)"
        if not (lead.get("seller_phone") or "").strip()
        else "On file (restricted - not printed for privacy in package sample)",
    )

    _section(pdf, "4. Value estimates (NOT an appraisal)")
    _line(pdf, "Stored Estimated ARV:", f"{_money(arv)}  [{avail['arv']}]")
    _line(pdf, "Defensible preliminary ARV:", f"{_money(defensible_arv)}  [reconciled - see sec 5]")
    _line(
        pdf,
        "MAO at defensible ARV:",
        f"{_money(mao_defensible['computed_mao'])}  [recalculated]",
    )
    _line(pdf, "Stored Suggested MAO:", f"{_money(mao)}  [{avail['mao']}]")
    _line(pdf, "Assignment fee target:", f"{_money(fee)}  [{avail['wholesale_fee']}]")
    if repairs > 0:
        _line(
            pdf,
            "Repairs estimate:",
            f"{_money(repairs)}  [estimate - not a site inspection; stored DealShark rehab assumption]",
        )
    else:
        _line(pdf, "Repairs estimate:", "Not available  [missing]")
    _line(
        pdf,
        "Last sale price:",
        f"{_money(last_sale)}  "
        f"[{'available' if last_sale > 0 else 'missing'}]",
    )
    if equity > 0:
        _line(pdf, "Potential equity:", f"{_money(equity)}  [estimate]")
    else:
        _line(
            pdf,
            "Potential equity:",
            "Not available - mortgage payoff / liens / last sale not verified",
        )

    _section(pdf, "5. Valuation reconciliation")
    pdf.multi_cell(0, 4.5, _ascii(str(recon.get("basis_note") or "")), new_x="LMARGIN", new_y="NEXT")
    if _as_float(recon.get("tax_assessed")) > 0:
        _line(
            pdf,
            "Tax assessment anchor:",
            f"{_money(recon.get('tax_assessed'))} ({recon.get('tax_assessed_year') or 'n/a'})",
        )
    if _as_float(recon.get("naive_filtered_arv")) > 0:
        _line(
            pdf,
            "Naive filtered-comp average:",
            (
                f"{_money(recon.get('naive_filtered_arv'))} "
                f"(~${_as_float(recon.get('naive_avg_pps')):,.0f}/sf) - NOT adopted automatically"
            ),
        )
    if _as_float(recon.get("core_median_arv")) > 0:
        _line(
            pdf,
            "CORE-comp median (ex-superior):",
            f"{_money(recon.get('core_median_arv'))}",
        )
    if _as_float(recon.get("core_adj_arv")) > 0:
        _line(
            pdf,
            "CORE comps after location/age $/sf haircuts:",
            f"{_money(recon.get('core_adj_arv'))}",
        )
    if _as_float(recon.get("upside_if_condition_supports")) > 0:
        _line(
            pdf,
            "Upside band (IF condition/reno verified):",
            f"up to ~{_money(recon.get('upside_if_condition_supports'))} - not package ARV",
        )
    _line(pdf, "Defensible preliminary ARV:", _money(defensible_arv))
    pdf.multi_cell(0, 4.5, _ascii(str(recon.get("rationale") or "")), new_x="LMARGIN", new_y="NEXT")
    _line(pdf, "MAO formula:", mao_defensible["formula"])
    flood_buf = _as_float(mao_defensible.get("flood_buffer"))
    flood_bit = (
        f" - {_money(flood_buf)} zip risk buffer"
        if flood_buf > 0
        else " - $0 zip risk buffer"
    )
    _line(
        pdf,
        "MAO at defensible ARV:",
        (
            f"( {_money(defensible_arv)} x {int(DEFAULT_MARKET_FACTOR * 100)}% ) - "
            f"{_money(repairs)} repairs - {_money(fee)} fee - "
            f"{_money(mao_defensible['closing'])} closing "
            f"(3% of ARV {_money(defensible_arv)}, not of MAO)"
            f"{flood_bit} "
            f"= {_money(mao_defensible['computed_mao'])}"
        ),
    )
    if flood_buf > 0 and mao_defensible.get("flood_note"):
        _line(pdf, "Zip risk buffer note:", str(mao_defensible.get("flood_note")))
    if repairs <= 0:
        _line(
            pdf,
            "Repairs in MAO math:",
            "No repair-cost estimate on file - MAO uses $0 repairs (not a verified as-is condition).",
        )
    if abs(mao - mao_defensible["computed_mao"]) < 2.0:
        _line(pdf, "Stored MAO check:", "Matches formula above (including zip buffer when applicable).")
    else:
        _line(
            pdf,
            "Stored MAO vs recalculated:",
            f"Stored {_money(mao)} vs {_money(mao_defensible['computed_mao'])} at defensible ARV. "
            "Prefer the recalculated figure unless a documented extra haircut is on file.",
        )
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0,
        4,
        _ascii(
            "Uncertainty: no verified condition, renovation level, or interior photos. "
            "Distance figures from the comps feed may be rounded. "
            "Investors must re-underwrite before relying on any ARV."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    _section(pdf, "6. Comparable sales (quality-tiered)")
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, _ascii(comps_note), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    annotated = recon.get("annotated_comps") or []
    if not annotated:
        pdf.multi_cell(
            0,
            5,
            _ascii(
                "No underwriting-quality comps remaining after filters. "
                "Raw outliers (missing specs, extreme prices, size mismatches) were excluded rather than shown."
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
    else:
        for i, c in enumerate(annotated, 1):
            sale = str(c.get("sale_date") or "date n/a")
            if "T" in sale:
                sale = sale.split("T", 1)[0]
            year = c.get("year") or c.get("yearBuilt") or "?"
            line = (
                f"{i}. [{str(c.get('tier') or '').upper()}] {c.get('address') or 'Comp'} | "
                f"sold {_money(c.get('sold_price'))} on {sale} | "
                f"{c.get('sqft') or '?'} sf | "
                f"{c.get('beds')}/{c.get('baths')} | yr {year} | "
                f"${_as_float(c.get('pps')):,.0f}/sf "
                f"(adj ~${_as_float(c.get('adj_pps')):,.0f}/sf) | "
                f"{c.get('distance') or ''}"
            )
            pdf.multi_cell(0, 4.5, _ascii(line), new_x="LMARGIN", new_y="NEXT")
            notes = c.get("notes") or []
            if notes:
                pdf.set_font("Helvetica", "I", 8)
                pdf.multi_cell(
                    0,
                    3.8,
                    _ascii("    Adjustments: " + "; ".join(str(n) for n in notes)),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.set_font("Helvetica", size=9)
    if rejected:
        pdf.set_font("Helvetica", "I", 8)
        pdf.multi_cell(
            0,
            4,
            _ascii(
                "Hard-excluded before tiering (missing specs / extreme outliers): "
                + "; ".join(rejected[:4])
                + (" ..." if len(rejected) > 4 else "")
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

    _section(pdf, "7. Risk factors")
    _line(pdf, "Risk level:", str(lead.get("risk_level") or "Standard"))
    _flag_line(pdf, "Flood risk zip:", "Yes" if lead.get("flood_risk") else "No", verified=False)
    _flag_line(
        pdf,
        "Tax delinquent flag:",
        "Yes" if lead.get("tax_delinquent") else "No",
        verified=False,
    )
    _flag_line(
        pdf,
        "Code violation flag:",
        "Yes" if lead.get("code_violation") else "No",
        verified=False,
    )
    _flag_line(pdf, "Probate flag:", "Yes" if lead.get("probate") else "No", verified=False)
    fc = (lead.get("foreclosure_case") or "").strip()
    if fc:
        _flag_line(pdf, "Foreclosure case:", fc, verified=True)
    else:
        _flag_line(pdf, "Foreclosure case:", "None on file", verified=False)
    _line(pdf, "Unpaid taxes $:", _money(lead.get("unpaid_taxes")))
    _line(pdf, "Municipal liens $:", _money(lead.get("municipal_liens")))
    _line(pdf, "HOA dues $:", _money(lead.get("hoa_dues")))
    score = int(lead.get("motivation_score") or 0)
    _line(
        pdf,
        "Motivation score:",
        f"{score}/100 ({lead.get('motivation_tier') or 'n/a'}) - internal DealShark score, not verified seller intent",
    )
    tags = (lead.get("motive_tags") or "").strip()
    if tags:
        _line(pdf, "Tags:", tags)

    _section(pdf, "8. Field availability checklist")
    for k, v in avail.items():
        _line(pdf, f"{k}:", v)

    _section(pdf, "9. Research scope")
    pdf.multi_cell(
        0,
        4.5,
        _ascii(
            "This PDF is research documentation only. "
            "It is not a contracted deal, not an offer to sell, and not confirmation that "
            "the property is vacant, distressed, or available. "
            "No seller or investor outreach is performed by generating this report."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return pdf


def generate_investor_report(
    lead: dict[str, Any],
    *,
    output_dir: Path | None = None,
    include_live_comps: bool = True,
) -> Path:
    out_dir = output_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    lead_id = lead.get("id") or "X"
    slug = _street_slug(str(lead.get("address") or "PROPERTY"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"INVESTOR_REPORT_{lead_id}_{slug}_{stamp}.pdf"
    pdf = build_investor_report_pdf(lead, include_live_comps=include_live_comps)
    pdf.output(str(path))
    return path


def generate_package_cover(
    leads: list[dict[str, Any]],
    *,
    output_dir: Path | None = None,
) -> Path:
    out_dir = output_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"DEALSHARK_PACKAGE_COVER_{stamp}.pdf"
    pdf = build_package_cover_pdf(leads)
    pdf.output(str(path))
    return path


def generate_investor_reports_batch(
    leads: list[dict[str, Any]],
    *,
    output_dir: Path | None = None,
    include_live_comps: bool = True,
    make_zip: bool = True,
) -> dict[str, Any]:
    """Generate cover + one PDF per lead; optional zip. No contact/outreach."""
    out_dir = output_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    errors: list[str] = []

    try:
        cover = generate_package_cover(leads, output_dir=out_dir)
        paths.append(cover)
    except Exception as exc:
        errors.append(f"cover: {exc}")

    for lead in leads:
        try:
            paths.append(
                generate_investor_report(
                    lead,
                    output_dir=out_dir,
                    include_live_comps=include_live_comps,
                )
            )
        except Exception as exc:
            errors.append(f"#{lead.get('id')}: {exc}")

    zip_path: Path | None = None
    if make_zip and paths:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = out_dir / f"DEALSHARK_TAMPA_RESEARCH_PACK_{stamp}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in paths:
                zf.write(p, arcname=p.name)

    return {
        "ok": bool(paths),
        "paths": paths,
        "zip_path": zip_path,
        "errors": errors,
        "count": len([p for p in paths if p.name.startswith("INVESTOR_REPORT_")]),
    }
