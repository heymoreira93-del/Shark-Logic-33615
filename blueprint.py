"""
DealShark Zombie / Assignment Blueprint — scoring + phase checklist.

Zombie property = appears abandoned/distress (foreclosure walkaway, vacant,
code issues) but the owner of record may still legally own it. Never treat
vacant-looking as ownerless.

MAO = ARV - repairs - buyer_profit_cushion - assignment_fee
(then adjust for liens, taxes, HOA, title defects, access).
"""

from __future__ import annotations

from typing import Any

# 12-phase operating pipeline (assignment / wholesaling)
BLUEPRINT_PHASES: list[dict[str, str]] = [
    {
        "id": "1",
        "name": "Build lead list",
        "do": "Vacant/absentee, code-violation, tax-delinquent, pre-foreclosure, probate, utility-disconnect, boarded, tired landlord",
        "out": "100–500 target properties",
        "app": "Seller Factory · CSV import · War Room",
    },
    {
        "id": "2",
        "name": "Verify property",
        "do": "Parcel, owner of record, mailing, mortgage/FC status, taxes, liens, HOA, code, occupancy",
        "out": "Clean lead record",
        "app": "Pull Live Data (RentCast) · War Room zombie fields",
    },
    {
        "id": "3",
        "name": "Find the owner",
        "do": "Lawful skip-trace; mail/call/text where permitted",
        "out": "Owner contact",
        "app": "Skip Trace · Seller cell/email · paste if no BatchData credits",
    },
    {
        "id": "4",
        "name": "Qualify distress",
        "do": "Condition, timeline, mortgage, liens, ask, access, reason",
        "out": "Motivated seller score",
        "app": "Motivation score · Lead Heat · War Room notes",
    },
    {
        "id": "5",
        "name": "Estimate value",
        "do": "ARV from nearby sold comps (not listings alone)",
        "out": "ARV",
        "app": "Pull Live Data · comps table",
    },
    {
        "id": "6",
        "name": "Estimate repairs",
        "do": "Roof, HVAC, electric, plumbing, foundation, mold, windows, kitchen/bath, trash-out, permits",
        "out": "Repair budget",
        "app": "Repair Checklist · rehab engine",
    },
    {
        "id": "7",
        "name": "Calculate offer",
        "do": "Back into price leaving rehab, holding, closing, buyer profit, your fee",
        "out": "MAO",
        "app": "Shark MAO · Aggressive/Mid/Safe",
    },
    {
        "id": "8",
        "name": "Contract property",
        "do": "State-appropriate PSA allowing assignment; disclose role",
        "out": "Executed contract",
        "app": "Generate PDF · Fire SMS · e-sign",
    },
    {
        "id": "9",
        "name": "Title immediately",
        "do": "Investor-friendly title/attorney; lien search",
        "out": "Clear-to-close / problem list",
        "app": "Build Title Packet · title_status field",
    },
    {
        "id": "10",
        "name": "Build buyer package",
        "do": "Photos, address, ARV, comps, repairs, ask, access, title status",
        "out": "Deal package",
        "app": "Deal alert email · War Room deal card",
    },
    {
        "id": "11",
        "name": "Dispo to buyers",
        "do": "Vetted cash buyers / landlords / rehabbers; POF when appropriate",
        "out": "End buyer",
        "app": "VERIFY & BLAST · buyer_status",
    },
    {
        "id": "12",
        "name": "Assign/close",
        "do": "Assignment agreement, EMD, close through title",
        "out": "Assignment fee",
        "app": "Assignment PDF · Stripe EMD · close checklist",
    },
]

TITLE_STATUSES = (
    "Not Sent",
    "Ordered",
    "Issues",
    "Clear to Close",
    "Closed",
)

BUYER_STATUSES = (
    "None",
    "Packaged",
    "Blasted",
    "Interested",
    "POF Received",
    "Assigned",
    "Dead",
)

OWNER_CONTACT_STATUSES = (
    "Unknown",
    "Mailing Only",
    "Phone Found",
    "Email Found",
    "Reached",
    "No Contact",
    "Do Not Contact",
)


def calculate_mao_ceiling(
    arv: float,
    repairs: float,
    buyer_cushion: float,
    assignment_fee: float,
) -> float:
    """
    MAO = ARV - repairs - buyer profit/holding/closing cushion - assignment fee.
    Still adjust for liens/taxes/HOA/title/access outside this formula.
    """
    return float(arv) - float(repairs) - float(buyer_cushion) - float(assignment_fee)


def score_zombie_lead(
    *,
    vacant: bool = False,
    absentee: bool = False,
    code_violation: bool = False,
    tax_delinquent: bool = False,
    foreclosure_case: str = "",
    unpaid_taxes: float = 0.0,
    municipal_liens: float = 0.0,
    hoa_dues: float = 0.0,
    probate: bool = False,
    estimated_equity: float = 0.0,
    owner_contact_status: str = "Unknown",
    arv: float = 0.0,
    mao: float = 0.0,
) -> dict[str, Any]:
    """
    Score distress + equity + reachable ownership + title path.

    High score alone is not a green light — liens/FC payoff can wipe equity.
    """
    score = 0
    tags: list[str] = []

    if vacant:
        score += 18
        tags.append("Vacant/zombie look")
    if absentee:
        score += 12
        tags.append("Absentee")
    if code_violation:
        score += 14
        tags.append("Code violation")
    if tax_delinquent or unpaid_taxes > 0:
        score += 16
        tags.append("Tax delinquent")
    if (foreclosure_case or "").strip():
        score += 20
        tags.append("Foreclosure case")
    if probate:
        score += 10
        tags.append("Probate/heirs")
    if municipal_liens > 0:
        score += 8
        tags.append("Municipal liens")
    if hoa_dues > 0:
        score += 6
        tags.append("HOA")

    # Equity path — distress without equity is a trap
    if estimated_equity >= 80000:
        score += 20
        tags.append("Strong equity")
    elif estimated_equity >= 40000:
        score += 12
        tags.append("Moderate equity")
    elif estimated_equity > 0:
        score += 4
        tags.append("Thin equity")
    elif arv > 0 and mao > 0 and mao < arv * 0.55:
        # MAO far under ARV often implies room — weak proxy only
        score += 6
        tags.append("MAO room (proxy)")

    contact = (owner_contact_status or "Unknown").strip()
    if contact in {"Phone Found", "Email Found", "Reached"}:
        score += 15
        tags.append(f"Contact: {contact}")
    elif contact == "Mailing Only":
        score += 6
        tags.append("Mailing only")
    elif contact == "Do Not Contact":
        score -= 25
        tags.append("Do Not Contact")

    # Drag when debt stack looks heavy vs ARV
    debt_stack = float(unpaid_taxes or 0) + float(municipal_liens or 0) + float(hoa_dues or 0)
    if arv > 0 and debt_stack >= arv * 0.25:
        score -= 18
        tags.append("Heavy liens vs ARV")

    score = max(0, min(100, int(score)))
    if score >= 70:
        tier = "Hot"
    elif score >= 45:
        tier = "Warm"
    elif score >= 25:
        tier = "Watch"
    else:
        tier = "Cold"

    return {
        "motivation_score": score,
        "tier": tier,
        "tags": tags,
        "debt_stack": round(debt_stack, 2),
        "warning": (
            "Looks distressed but debt/title may consume equity - verify payoff before offer."
            if debt_stack > 0 or (foreclosure_case or "").strip()
            else ""
        ),
    }


def render_blueprint_panel() -> None:
    """Streamlit: 12-phase blueprint + MAO formula reminder."""
    import streamlit as st

    st.subheader("Zombie Assignment Blueprint")
    st.caption(
        "Operating map for Tampa assignment/wholesaling. "
        "Abandoned-looking ≠ ownerless. Confirm owner of record and title path."
    )

    st.markdown(
        "**MAO** = ARV − repairs − buyer profit/holding/closing cushion − your assignment fee. "
        "Then cut for liens, taxes, HOA, title defects, and access risk."
    )

    example = calculate_mao_ceiling(250000, 55000, 45000, 10000)
    st.info(
        f"Example only: ARV $250k − repairs $55k − cushion $45k − fee $10k → "
        f"ceiling **${example:,.0f}** (still adjust for liens/title)."
    )

    rows = [
        {
            "Phase": p["id"],
            "Name": p["name"],
            "Do": p["do"],
            "Output": p["out"],
            "In DealShark": p["app"],
        }
        for p in BLUEPRINT_PHASES
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown(
        "**Lead record fields:** address, owner, mailing, occupancy/vacant, "
        "foreclosure case, lender, unpaid taxes, municipal liens, code violations, "
        "probate, HOA, estimated equity, last sale, ARV, repairs, owner contact, "
        "motivation score, offer/MAO, contract status, title status, buyer status."
    )
    st.caption(
        "Florida: do not confuse Ch. 717 abandoned personal property with abandoned real estate. "
        "Assignment recording rules still apply — disclose your role; use title/attorney."
    )
