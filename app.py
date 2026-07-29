"""
DealShark — Tampa Shark Mode
Calculator tab + Tampa War Room tab + Seller signing view.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

from secrets_bootstrap import bootstrap_secrets

bootstrap_secrets()

from comms import notify_deal_signed, send_offer_sms, signing_url
from contract_gen import generate_assignment_pdf
from crm import add_lead as crm_add_lead
from crm import get_leads as crm_get_leads
from crm import get_stale_leads
from crm import init_db as init_crm_db
from crm import pipeline_snapshot
from crm import update_contact_date
from crm import update_contact_date_by_id
from data_engine import extract_zip, get_tampa_comps, get_tampa_data, has_rentcast_key
from database import init_db as init_tampa_db
from database import save_lead
from db import (
    LEAD_TEMPS,
    append_note,
    create_deal,
    get_deal,
    init_db,
    list_deals,
    mark_as_signed,
    update_lead_temp,
)
from generator import generate_contract
from hunter import skip_trace
from tampa_config import DEFAULT_CLOSING_COST_PCT, MANUAL_FLOOD_MAO_HIT
from rehab import (
    apply_tampa_risk_adjustments,
    calculate_rehab,
    florida_doc_stamps,
    repair_options,
    shark_mao,
    tampa_hazard_check,
)
from tampa_leads import mock_tampa_offmarket_leads, prepare_recent_filings_parse
from war_room import render_war_room

st.set_page_config(page_title="DealShark Tampa", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    div[data-testid="stMetricValue"] { font-size: 1.9rem; color: #3ddc97; }
    .block-container { padding-top: 1.2rem; max-width: 1200px; }
    </style>
    """,
    unsafe_allow_html=True,
)

init_db()
init_tampa_db()
init_crm_db()

# ---------------------------------------------------------------------------
# Seller View (?deal_id=)
# ---------------------------------------------------------------------------
query_params = st.query_params
if "deal_id" in query_params:
    deal_id = query_params["deal_id"]
    if isinstance(deal_id, list):
        deal_id = deal_id[0]
    deal = get_deal(str(deal_id))
    st.header("Real Estate Purchase Agreement")
    if not deal:
        st.error("Deal not found.")
        st.stop()
    st.info(f"Property: {deal['address']}")
    st.success(f"Offer Amount: ${deal['price']:,.2f}")
    st.write(f"**Seller on file:** {deal['seller_name']}")
    pdf_path = deal.get("pdf_path") or ""
    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, "rb") as f:
            st.download_button(
                "View Offer PDF",
                f,
                file_name=Path(pdf_path).name,
                mime="application/pdf",
                use_container_width=True,
            )
    if deal.get("status") == "SIGNED":
        st.success(f"Document already signed by **{deal.get('signature') or 'Seller'}**.")
        st.stop()
    st.write("By typing your name below, you agree to the terms of the purchase agreement.")
    sig = st.text_input("Type Full Legal Name (Electronic Signature)")
    if st.button("Accept & Sign Offer", type="primary", use_container_width=True):
        if sig and sig.strip():
            if mark_as_signed(str(deal_id), sig.strip()):
                notify_deal_signed(
                    address=deal["address"],
                    price=float(deal["price"]),
                    signature_name=sig.strip(),
                    deal_id=str(deal_id),
                )
                st.balloons()
                st.success("Document Signed! We will contact you shortly to open escrow.")
            else:
                st.error("Could not sign this deal (it may already be signed).")
        else:
            st.error("Please sign the document to proceed.")
    st.stop()

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
for key, default in {
    "seller_name": "",
    "seller_phone": "",
    "seller_email": "",
    "last_deal_id": "",
    "last_pdf_path": "",
    "arv": 300000.0,
    "sqft": 1500.0,
    "zip_code": "",
    "comps": [],
    "year_built": None,
    "avg_sqft_price": 0.0,
    "data_source": "manual",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.title("DealShark — Tampa Shark Mode")
st.caption("Live RentCast · Flood Guard · War Room · Bulk SMS. Built for the 813.")

# Sidebar (shared)
st.sidebar.header("Tampa Strategy")
fee = st.sidebar.number_input("Wholesale Fee ($)", value=10000, step=1000, min_value=10000)
st.sidebar.caption("Tampa floor: $10k minimum fee.")
market_factor = st.sidebar.slider("Market Factor (%)", 60, 85, 70) / 100
buyer_name = st.sidebar.text_input("Buyer Name", value="DealShark Acquisitions")
emd = st.sidebar.number_input("Earnest Money ($)", value=1000, step=100)
closing_days = st.sidebar.number_input("Close in (days)", 7, 90, 21)
inspection_days = st.sidebar.number_input("Inspection Days", 1, 30, 7)
closing_pct = st.sidebar.slider("Closing Costs %", 1.0, 5.0, DEFAULT_CLOSING_COST_PCT * 100, 0.5) / 100

if has_rentcast_key():
    st.sidebar.success("RentCast API key detected — live data ON.")
else:
    st.sidebar.warning("No RentCast key — mock data. Add RENTCAST_API_KEY to `.env`.")

st.sidebar.markdown("---")
st.sidebar.title("33615 Pipeline")
_crm = pipeline_snapshot()
st.sidebar.metric("Potential Payday (Under Contract)", f"${_crm['under_contract_fees']:,.2f}")
st.sidebar.metric("Offered Fees (pipeline)", f"${_crm['offered_fees']:,.2f}")
if _crm["recent"]:
    st.sidebar.subheader("Recent Sharks")
    for row in _crm["recent"]:
        st.sidebar.write(f"{row.get('address', '—')} — {row.get('status', '')}")
else:
    st.sidebar.write("No deals in the water yet. Start hunting.")

st.sidebar.markdown("---")
st.sidebar.subheader("Shark Alerts (Follow-Up)")
st.sidebar.caption("Red = not contacted in 72 hours. Fortune is in the follow-up.")
_stale = get_stale_leads(72)
if not _stale.empty:
    st.sidebar.error(f"{len(_stale)} lead(s) need a redial")
    for _, lead in _stale.iterrows():
        addr = str(lead.get("address") or "Unknown")
        name = str(lead.get("name") or "Seller")
        try:
            lid = int(lead["id"])
        except (TypeError, ValueError, KeyError):
            lid = None
        st.sidebar.error(f"Redial: {addr}")
        btn_key = f"log_call_{lid if lid is not None else addr}"
        if st.sidebar.button(f"Log Call: {name}", key=btn_key):
            if lid is not None:
                update_contact_date_by_id(lid)
            else:
                update_contact_date(addr)
            st.rerun()
else:
    st.sidebar.success("All leads are fresh. Go get new ones.")

calc_tab, war_tab = st.tabs(["Calculator", "Tampa War Room"])

# ===========================================================================
# TAB: War Room
# ===========================================================================
with war_tab:
    render_war_room(buyer_name=buyer_name.strip() or "DealShark")

# ===========================================================================
# TAB: Calculator
# ===========================================================================
with calc_tab:
    with st.expander("How to use this app (step by step)", expanded=False):
        st.markdown(
            """
1. Enter a Tampa address → **Pull Live Data**
2. Confirm ARV / repairs / flood flags
3. **Save Lead to War Room** (or Generate PDF / Fire SMS)
4. Open **Tampa War Room** tab → follow up / bulk SMS
            """
        )

    hunt, math_col, kill = st.columns(3)

    with hunt:
        st.subheader("The Hunt")
        st.caption("Address → Live Data → Skip Trace")
        address = st.text_input(
            "Property Address",
            placeholder="815 E Lake Ave, Tampa, FL 33603",
            key="calc_address",
        )

        b1, b2 = st.columns(2)
        with b1:
            pull_live = st.button("Pull Live Data", type="primary", use_container_width=True)
        with b2:
            do_trace = st.button("Skip Trace", use_container_width=True)

        if pull_live:
            if not address.strip():
                st.error("Enter a Tampa address first.")
            else:
                with st.spinner("Hitting RentCast / comps..."):
                    bundle = get_tampa_data(address.strip())
                if bundle.get("error"):
                    st.error(bundle["error"])
                else:
                    st.session_state.arv = float(bundle.get("arv") or st.session_state.arv)
                    st.session_state.sqft = float(bundle.get("sqft") or 1500)
                    st.session_state.zip_code = str(bundle.get("zipCode") or "")
                    st.session_state.comps = bundle.get("comps") or []
                    st.session_state.year_built = bundle.get("yearBuilt")
                    st.session_state.avg_sqft_price = float(bundle.get("avg_sqft_price") or 0)
                    st.session_state.data_source = bundle.get("source", "rentcast")
                    st.success(
                        f"Loaded · ARV ${st.session_state.arv:,.0f} · "
                        f"{st.session_state.sqft:,.0f} sqft · "
                        f"source={st.session_state.data_source}"
                    )

        if do_trace:
            if not address.strip():
                st.error("Enter an address first.")
            else:
                hit = skip_trace(address.strip())
                if hit:
                    st.session_state.seller_name = hit.get("owner_name") or ""
                    st.session_state.seller_phone = hit.get("phone") or ""
                    st.session_state.seller_email = hit.get("email") or ""
                    st.success(f"Located: **{st.session_state.seller_name}**")
                else:
                    st.error("Skip trace returned nothing.")

        seller_name = st.text_input("Seller Name", value=st.session_state.seller_name, key="calc_seller")
        st.session_state.seller_name = seller_name

        mobile = st.text_input(
            "Twilio Mobile #",
            value=st.session_state.seller_phone,
            placeholder="+15551234567",
            key="calc_mobile",
        )
        st.session_state.seller_phone = mobile

        sqft = st.number_input(
            "Square Footage",
            value=float(st.session_state.sqft or 1500),
            step=50.0,
            key="calc_sqft",
        )
        st.session_state.sqft = sqft

        lead_temp = st.radio("Lead Heat", list(LEAD_TEMPS), index=0, horizontal=True, key="calc_heat")

    with math_col:
        st.subheader("The Math")
        st.caption("ARV + Tampa repairs + flood risk")

        zip_guess = st.session_state.zip_code or extract_zip(address)
        hazard = tampa_hazard_check(zip_guess)

        flood_toggle = st.toggle(
            "Flood Zone (manual)",
            value=bool(hazard.get("is_flood_zip")),
            help="Auto-ON for known South Tampa / coastal zips.",
            key="calc_flood",
        )
        hvhz = st.toggle("High-Velocity Hurricane Zone (HVHZ)", value=False, key="calc_hvhz")

        # Shark Alert UI — elevated/high = error, moderate = warning, else success
        if hazard.get("buffer_deduction", 0) > 0 or flood_toggle:
            tier = hazard.get("tier") or "high"
            risk_label = hazard.get("risk_level") or "HIGH (Flood Zone - manual)"
            buffer_shown = float(
                hazard.get("buffer_deduction") or (MANUAL_FLOOD_MAO_HIT if flood_toggle else 0)
            )
            if tier == "moderate" and not flood_toggle:
                st.warning(f"{risk_label} DETECTED")
            else:
                st.error(f"{risk_label} DETECTED")
            st.write(
                f"Automatically deducted **${buffer_shown:,.0f}** from MAO for flood insurance buffer."
            )
            if hazard.get("warning"):
                st.caption(hazard["warning"])
        else:
            st.success("Property is in a Standard/Low-risk flood zone.")

        arv = st.number_input(
            "After Repair Value (ARV) ($)",
            value=float(st.session_state.arv or 300000),
            step=5000.0,
            key="calc_arv",
        )
        st.session_state.arv = arv

        confidence = st.slider("ARV Confidence", 70, 100, 95, key="calc_conf")
        effective_arv = arv * (confidence / 100.0)
        st.caption(f"Effective ARV: **${effective_arv:,.0f}** · Zip: **{zip_guess or '—'}**")

        selected_repairs = st.multiselect(
            "Repair Checklist",
            options=repair_options(),
            default=["Paint"],
            format_func=lambda x: {
                "Roof": "Roof ($8/sqft)",
                "Paint": "Paint ($3/sqft)",
                "Kitchen": "Kitchen ($15k)",
                "HVAC": "HVAC ($8k)",
                "Windows": "Windows ($12k, 1.5x if HVHZ)",
            }.get(x, x),
            key="calc_repairs",
        )
        rehab = calculate_rehab(selected_repairs, float(sqft), hvhz=hvhz)
        st.write(f"Rehab Total: **${rehab['total']:,.0f}**")
        for line in rehab["lines"]:
            st.caption(f"- {line['item']}: ${line['cost']:,.0f}")

        comps = st.session_state.comps or []
        if not comps and address.strip():
            comps = get_tampa_comps(address.strip(), zip_code=zip_guess)
            st.session_state.comps = comps

        with st.expander(f"Nearby Comps ({len(comps)})"):
            for c in comps:
                st.write(
                    f"{c.get('status', 'Sold')} · {c.get('address')} · "
                    f"${float(c.get('sold_price') or 0):,.0f} · {c.get('distance', '')}"
                )

    flood_buffer = 0.0
    if hazard.get("is_flood_zip"):
        flood_buffer = float(hazard.get("buffer_deduction") or 0)
    elif flood_toggle:
        flood_buffer = MANUAL_FLOOD_MAO_HIT

    with kill:
        st.subheader("The Kill")
        st.caption("Shark MAO → Save / PDF / SMS")
        offers = shark_mao(
            effective_arv,
            rehab["total"],
            fee,
            market_factor,
            flood_buffer=flood_buffer,
            closing_cost_pct=closing_pct,
        )
        mao = offers["Aggressive"]
        st.metric("Shark MAO (Cash Offer Cap)", f"${mao:,.2f}")
        st.caption(
            f"Mid ${offers['Mid']:,.0f} · Safe ${offers['Safe']:,.0f} · "
            f"Fee ${offers['fee_used']:,.0f} · Closing ${offers['closing_costs']:,.0f} · "
            f"Flood buffer ${offers['flood_buffer']:,.0f}"
        )
        st.caption(f"FL doc stamps (est.): ${florida_doc_stamps(mao):,.0f}")

        offer_choice = st.radio(
            "Offer Tier", ["Aggressive", "Mid", "Safe"], horizontal=True, key="calc_tier"
        )
        offer_price = offers[offer_choice]

        save_lead_btn = st.button("Save Lead to War Room", use_container_width=True)
        gen_pdf = st.button("Generate PDF", type="primary", use_container_width=True)
        fire_sms = st.button("Fire SMS Offer / Shark Offer", use_container_width=True)

    closing_date = (datetime.now() + timedelta(days=int(closing_days))).strftime("%Y-%m-%d")

    def _persist_war_room_lead(status: str = "New Lead") -> int:
        """Glue: Flood Guard + current calculator numbers → tampa_leads.db."""
        zip_code = zip_guess or extract_zip(address)
        # Base MAO before explicit flood re-check (shark_mao already applied buffer)
        hazard_adj = apply_tampa_risk_adjustments(zip_code, float(mao) + float(flood_buffer))
        # Prefer the live Shark MAO already shown (includes buffer + closing)
        final_mao = float(offer_price)
        risk = hazard_adj["risk_level"]
        if flood_toggle and not hazard_adj.get("is_flood_zip"):
            risk = "HIGH (Flood Zone - manual)"
        return save_lead(
            address=address.strip(),
            zip_code=zip_code,
            arv=float(effective_arv),
            mao=final_mao,
            fee=float(offers["fee_used"]),
            risk=risk,
            flood_risk=bool(hazard_adj.get("is_flood_zip") or flood_toggle),
            status=status,
            seller_name=seller_name.strip(),
            seller_phone=mobile.strip(),
        )

    if save_lead_btn:
        if not address.strip():
            st.error("Enter a property address.")
        else:
            lead_id = _persist_war_room_lead("New Lead" if lead_temp != "Hot" else "Hot Lead")
            hazard_adj = apply_tampa_risk_adjustments(zip_guess or extract_zip(address), mao)
            st.success(
                f"Lead #{lead_id} saved to War Room · Risk: {hazard_adj['risk_level']} · "
                f"MAO ${offer_price:,.0f}"
            )

    def _build_offer_artifacts() -> tuple[str, str]:
        pdf_path = str(
            generate_contract(
                address=address.strip(),
                seller=seller_name.strip() or "Seller",
                buyer=buyer_name.strip() or "DealShark Acquisitions",
                price=offer_price,
                emd=float(emd),
                closing_date=closing_date,
                inspection_days=int(inspection_days),
                expiration_date=datetime.now().date(),
                expiration_time="9:00 PM",
                scope_lines=rehab["lines"],
                comps=comps,
                rehab_total=rehab["total"],
                arv=effective_arv,
            )
        )
        deal_id = create_deal(
            address.strip(),
            offer_price,
            seller_name.strip() or "Seller",
            seller_phone=mobile.strip(),
            buyer_name=buyer_name.strip() or "DealShark Acquisitions",
            emd=float(emd),
            closing_date=closing_date,
            pdf_path=pdf_path,
            lead_temp=lead_temp,
            notes=f"Flood buffer ${flood_buffer:,.0f}; HVHZ={hvhz}; zip={zip_guess}",
        )
        st.session_state.last_pdf_path = pdf_path
        st.session_state.last_deal_id = deal_id
        return pdf_path, deal_id

    if gen_pdf:
        if not address.strip():
            st.error("Enter a property address.")
        else:
            pdf_path, deal_id = _build_offer_artifacts()
            _persist_war_room_lead("Offer Sent")
            st.success(f"PDF ready: `{pdf_path}`")
            st.info(f"Seller link: {signing_url(deal_id)}")
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "Download PDF",
                    f,
                    file_name=Path(pdf_path).name,
                    mime="application/pdf",
                    use_container_width=True,
                )

    if fire_sms:
        if not address.strip():
            st.error("Enter a property address.")
        elif not mobile.strip():
            st.error("Enter Twilio Mobile # (or Skip Trace first).")
        else:
            pdf_path = st.session_state.last_pdf_path
            if not pdf_path or not Path(pdf_path).exists():
                pdf_path, _ = _build_offer_artifacts()
            sid, deal_id = send_offer_sms(
                mobile.strip(),
                address.strip(),
                offer_price,
                deal_id=None,
                seller_name=seller_name.strip() or "Seller",
                buyer_name=buyer_name.strip() or "DealShark",
                create_if_missing=True,
                pdf_path=pdf_path,
                emd=float(emd),
                closing_date=closing_date,
                lead_temp=lead_temp,
            )
            _persist_war_room_lead("Offer Sent")
            if deal_id:
                st.session_state.last_deal_id = deal_id
                st.session_state.last_pdf_path = pdf_path
            if sid:
                st.toast("SMS fired.", icon="✅")
                st.success(f"SMS sent. SID: `{sid}`")
                st.code(signing_url(deal_id or ""))
            else:
                st.error("SMS failed. Check Twilio keys in `.env`.")
                if deal_id:
                    st.info(f"Deal saved. Seller link: {signing_url(deal_id)}")

    # ----- Deal Closer / Assignment Payday -----
    st.markdown("---")
    st.subheader("Deal Closer — The Payday")
    st.caption(
        "Lock the house at Shark MAO, find a cash buyer, assign for your fee. "
        "PDF saves to contracts/ for your ledger."
    )
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        assignment_fee = st.number_input(
            "Your Assignment Fee ($)",
            value=10000,
            step=1000,
            min_value=0,
            key="assign_fee",
        )
    with dc2:
        cash_buyer = st.text_input(
            "Cash Buyer Name",
            value="KINGPIN PROPERTIES LLC",
            key="cash_buyer",
        )
    with dc3:
        st.metric("Contract / Shark Offer", f"${offer_price:,.0f}")
        st.caption(f"Spread if assigned: **${assignment_fee:,.0f}**")

    closer_a, closer_b = st.columns(2)
    with closer_a:
        gen_assign = st.button("Generate Assignment PDF", type="primary", use_container_width=True)
    with closer_b:
        log_crm = st.button("Log to CRM (Offered)", use_container_width=True)

    if gen_assign:
        if not address.strip():
            st.error("Enter a property address first.")
        else:
            path = generate_assignment_pdf(
                address.strip(),
                cash_buyer.strip() or "TBD",
                float(assignment_fee),
                assignor_name=buyer_name.strip() or "DealShark Acquisitions",
                purchase_price=float(offer_price),
            )
            st.success(
                f"Contract ready in `contracts/` — send to title to secure your "
                f"${assignment_fee:,.0f} fee."
            )
            st.balloons()
            with path.open("rb") as f:
                st.download_button(
                    "Download Contract & Get Paid",
                    f,
                    file_name=path.name,
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_assign",
                )

    if log_crm:
        if not address.strip():
            st.error("Enter a property address first.")
        else:
            crm_id = crm_add_lead(
                name=seller_name.strip() or "Seller",
                address=address.strip(),
                status="Offered",
                mao=float(offer_price),
                fee=float(assignment_fee),
                zip_code=zip_guess or extract_zip(address),
                buyer_name=cash_buyer.strip(),
            )
            st.success(f"CRM #{crm_id} logged as Offered · fee ${assignment_fee:,.0f}")

    crm_df = crm_get_leads()
    if not crm_df.empty:
        with st.expander("CRM ledger (assignment deals)"):
            st.dataframe(crm_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Tampa Off-Market Prep (Hillsborough Clerk)")
    lead_url = st.text_input("Recent Filings results URL (optional)", key="filings_url")
    if st.button("Prep Parse Filings URL"):
        result = prepare_recent_filings_parse(lead_url)
        if result.get("ok"):
            st.success(f"Reachable · HTTP {result.get('status_code')}")
            st.json({k: result[k] for k in result if k != "ok"})
        else:
            st.error(result.get("error", "Failed"))

    with st.expander("Demo off-market lead ideas"):
        for row in mock_tampa_offmarket_leads():
            st.write(f"**{row['type']}** · {row['area']} — {row['note']}")

    st.markdown("---")
    st.subheader("Morning Pipeline (Contracts)")
    st.caption("Signed-deal notes from click-to-sign offers.")
    deals = list_deals(40)
    if not deals:
        st.info("No contract deals yet.")
    else:
        for d in deals:
            heat = d.get("lead_temp") or "Cold"
            with st.expander(
                f"{heat} · {d.get('address')} · ${float(d.get('price') or 0):,.0f}",
                expanded=False,
            ):
                st.write(f"ID `{d['id']}` · {d.get('seller_name')} · {d.get('seller_phone')}")
                st.code(signing_url(d["id"]))
                note = st.text_area("Add note", key=f"note_{d['id']}", height=70)
                if st.button("Log Note", key=f"log_{d['id']}"):
                    if append_note(d["id"], note):
                        st.rerun()
                new_temp = st.selectbox(
                    "Lead Heat",
                    list(LEAD_TEMPS),
                    index=list(LEAD_TEMPS).index(heat) if heat in LEAD_TEMPS else 0,
                    key=f"temp_{d['id']}",
                )
                if st.button("Save Heat", key=f"save_temp_{d['id']}"):
                    update_lead_temp(d["id"], new_temp)
                    st.rerun()
