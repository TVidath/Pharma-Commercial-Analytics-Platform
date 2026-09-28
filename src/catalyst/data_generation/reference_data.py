"""Static reference data for the synthetic pharma world.

These constants define the *structure* of the market (geography, portfolio,
specialties, channel economics). The behavioural magnitudes that create the
planted truths live in ``config/engagement_config.yaml``; the fixed catalogue
of entities lives here.
"""
from __future__ import annotations

# --- Geography: 25 regions across 4 zones, on real Indian states -------------
# (region_name, state, zone)
REGIONS = [
    # North (3)
    ("Delhi-NCR", "Delhi", "North"),
    ("UP-West", "Uttar Pradesh", "North"),
    ("UP-East", "Uttar Pradesh", "North"),
    # South (2)
    ("Bengaluru", "Karnataka", "South"),
    ("Chennai", "Tamil Nadu", "South"),
]
ZONES = ["North", "South"]

# Regions carrying the under-invested growth territories (planted truth P3):
# genuinely high-potential but staffed thin.
UNDERINVESTED_REGIONS = ["UP-East"]

# Zones under elevated competitive pressure (planted truth P6)
PRESSURED_ZONES = ["North"]
PRESSURED_TAS = ["Cardiology", "Diabetology"]

URBANICITY_TIERS = ["Metro", "Tier-1", "Tier-2", "Tier-3"]
URBANICITY_WEIGHTS = [0.14, 0.24, 0.34, 0.28]
# potential multiplier by urbanicity (bigger panels, more throughput in metros)
URBANICITY_POTENTIAL = {"Metro": 1.30, "Tier-1": 1.12, "Tier-2": 0.95, "Tier-3": 0.80}

# --- Therapeutic areas -------------------------------------------------------
# ta_name -> seasonality profile
THERAPEUTIC_AREAS = {
    "Cardiology": "Flat",
    "Diabetology": "Flat",
}

# --- Product portfolio (5 brands) -------------------------------------------
# brand, molecule, ta, form, unit_price, cost_per_unit, launch, lifecycle, base_size
# base_size = relative market weight (drives share of total volume)
PRODUCTS = [
    ("Cardizem-XR", "Amlodipine", "Cardiology", "Tablet", 85, 40, "2012-03", "Mature", 1.00),
    ("Lipivas", "Atorvastatin", "Cardiology", "Tablet", 120, 55, "2010-06", "Decline", 1.15),
    ("Clopigard", "Clopidogrel", "Cardiology", "Tablet", 160, 70, "2016-09", "Growth", 0.70),
    ("Glucomet-SR", "Metformin", "Diabetology", "Tablet", 65, 28, "2011-01", "Mature", 1.20),
    ("Gliptagon", "Sitagliptin", "Diabetology", "Tablet", 195, 80, "2017-04", "Growth", 0.80),
]

# --- Competitor brands (6) --------------------------------------------------
# competitor_brand, company, ta, unit_price
COMPETITORS = [
    ("Amlokind", "Rival Pharma A", "Cardiology", 80),
    ("Storvas", "Rival Pharma B", "Cardiology", 115),
    ("Deplatt", "Rival Pharma C", "Cardiology", 155),
    ("Glycomet", "Rival Pharma A", "Diabetology", 62),
    ("Januvia-G", "Rival Pharma D", "Diabetology", 205),
    ("Jardian-E", "Rival Pharma D", "Diabetology", 250),
]

# --- Specialties & product affinity -----------------------------------------
# specialty -> selection weight among 1,500 doctors
SPECIALTY_MIX = {
    "General Practitioner": 0.40,
    "Physician": 0.30,
    "Diabetologist": 0.15,
    "Cardiologist": 0.15,
}

# specialty -> list of brand names they prescribe (eligibility)
SPECIALTY_PRODUCTS = {
    "Cardiologist": ["Cardizem-XR", "Lipivas", "Clopigard"],
    "Diabetologist": ["Glucomet-SR", "Gliptagon"],
    "Physician": ["Cardizem-XR", "Lipivas", "Glucomet-SR", "Gliptagon"],
    "General Practitioner": ["Cardizem-XR", "Lipivas", "Glucomet-SR"],
}
# relative panel-size potential by specialty (specialists see denser panels)
SPECIALTY_POTENTIAL = {
    "Cardiologist": 1.25, "Diabetologist": 1.20,
    "Physician": 0.95, "General Practitioner": 0.80,
}

# --- Hospitals ---------------------------------------------------------------
HOSPITAL_TYPES = ["Corporate", "Private", "Government", "Nursing Home", "Clinic"]
HOSPITAL_TYPE_WEIGHTS = [0.08, 0.42, 0.20, 0.22, 0.08]
HOSPITAL_TYPE_BEDS = {  # (min, max) bed range by type
    "Corporate": (250, 900), "Private": (80, 350), "Government": (150, 1200),
    "Nursing Home": (20, 90), "Clinic": (0, 15),
}
HOSPITAL_TYPE_POTENTIAL = {
    "Corporate": 1.35, "Government": 1.15, "Private": 1.00,
    "Nursing Home": 0.80, "Clinic": 0.60,
}

# --- Marketing channels & economics (planted truth P5) ----------------------
# channel -> dict(budget_share, lead_rate_per_1000, conv_rate, promo_weight)
# ROI emerges in fact_marketing_spend as lead_rate * conv_rate * MARGIN_PER_CONVERSION/1000.
# Budget is deliberately skewed toward the low-ROI 'Print & Conferences'.
MARGIN_PER_CONVERSION = 5000.0  # INR gross margin attributed to a converted prescriber
MARKETING_CHANNELS = {
    "Print & Conferences": dict(budget_share=0.34, lead_rate=2.0, conv_rate=0.060, promo_weight=0.4),
    "Field Samples":       dict(budget_share=0.24, lead_rate=2.0, conv_rate=0.120, promo_weight=0.7),
    "Patient Programs":    dict(budget_share=0.16, lead_rate=2.2, conv_rate=0.136, promo_weight=0.9),
    "KOL Engagement":      dict(budget_share=0.14, lead_rate=2.5, conv_rate=0.176, promo_weight=1.1),
    "Digital & CME":       dict(budget_share=0.12, lead_rate=3.0, conv_rate=0.200, promo_weight=1.3),
}

# --- Name pools (synthetic Indian names) -------------------------------------
FIRST_NAMES = [
    "Rajesh", "Priya", "Amit", "Sunita", "Vikram", "Anita", "Suresh", "Kavita",
    "Arjun", "Deepa", "Manish", "Neha", "Rahul", "Pooja", "Sanjay", "Meera",
    "Karthik", "Divya", "Rohan", "Shalini", "Aditya", "Nisha", "Vivek", "Ritu",
    "Sameer", "Anjali", "Nikhil", "Swati", "Gaurav", "Preeti",
]
LAST_NAMES = [
    "Sharma", "Patel", "Reddy", "Nair", "Iyer", "Gupta", "Singh", "Rao",
    "Menon", "Desai", "Joshi", "Kulkarni", "Chatterjee", "Banerjee", "Mehta",
    "Shah", "Verma", "Kapoor", "Pillai", "Bose", "Naidu", "Malhotra", "Saxena",
    "Agarwal", "Bhat", "Chauhan", "Das", "Ghosh", "Kaur", "Mishra",
]
