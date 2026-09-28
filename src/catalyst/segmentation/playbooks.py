"""Segment-level action playbooks.

A segmentation is only as good as the action it drives. Each of the nine
doctor segments (Potential x Value) carries an explicit play: the investment
direction, call cadence, channel mix, and the KPI a rep is held to. This is
what turns an analytics artifact into a field instruction.
"""
from __future__ import annotations

from typing import Dict

# Investment direction used for the reallocation thesis.
INCREASE, MAINTAIN, REDUCE = "Increase", "Maintain", "Reduce / Efficient"

# (potential_tier, value_tier) -> segment definition
DOCTOR_SEGMENTS: Dict[tuple, Dict[str, str]] = {
    ("High", "High"): dict(
        name="Champions", action=MAINTAIN,
        objective="Protect the franchise; deepen breadth across the portfolio.",
        cadence="Sustain frequency; senior-rep / KOL engagement.",
        channels="Field + KOL + CME", kpi="Share of prescriptions; portfolio breadth"),
    ("High", "Medium"): dict(
        name="Rising Stars", action=INCREASE,
        objective="Accelerate conversion — genuine headroom above current value.",
        cadence="Increase call frequency; structured detailing.",
        channels="Field + Digital + Samples", kpi="Rx growth %; new-brand adoption"),
    ("High", "Low"): dict(
        name="Hidden Gems", action=INCREASE,
        objective="THE white space — high potential, under-developed. Convert.",
        cadence="Materially increase coverage & frequency.",
        channels="Field + Samples + Patient programs", kpi="First Rx; call-to-Rx conversion"),
    ("Medium", "High"): dict(
        name="Reliable Core", action=MAINTAIN,
        objective="Retain dependable volume; watch for competitor switching.",
        cadence="Maintain steady frequency.",
        channels="Field + Digital", kpi="Retention; share stability"),
    ("Medium", "Medium"): dict(
        name="Steady", action=MAINTAIN,
        objective="Hold and nudge; opportunistic up-sell of growth brands.",
        cadence="Standard frequency.",
        channels="Field + Digital", kpi="Rx growth %"),
    ("Medium", "Low"): dict(
        name="Developers", action=INCREASE,
        objective="Selectively develop where response is evident.",
        cadence="Test-and-learn frequency increase.",
        channels="Digital + Samples + selective field", kpi="Call-to-Rx conversion"),
    ("Low", "High"): dict(
        name="Loyal Small", action=REDUCE,
        objective="Efficient retention — high value but near ceiling; avoid over-servicing.",
        cadence="Reduce field calls; shift to lower-cost touch.",
        channels="Digital + periodic field", kpi="Cost-to-serve; retention"),
    ("Low", "Medium"): dict(
        name="Occasional", action=REDUCE,
        objective="Low-cost maintenance; limited upside.",
        cadence="Minimal field; digital-led.",
        channels="Digital", kpi="Cost per Rx"),
    ("Low", "Low"): dict(
        name="Low Priority", action=REDUCE,
        objective="Monitor only; free capacity for higher-opportunity doctors.",
        cadence="Digital-only / no active field.",
        channels="Digital", kpi="Cost avoidance"),
}

# Hospital tiers (potential-based)
HOSPITAL_TIERS: Dict[str, Dict[str, str]] = {
    "Platinum": dict(objective="Key-account plan; dedicated senior coverage; formulary access.",
                     action="Strategic invest"),
    "Gold": dict(objective="Structured coverage of affiliated high-potential doctors.",
                 action="Invest"),
    "Silver": dict(objective="Efficient coverage; grow selectively.",
                   action="Maintain"),
    "Bronze": dict(objective="Low-touch / digital; monitor for emerging potential.",
                   action="Monitor"),
}
