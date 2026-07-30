"""
Shared Tampa Bay config — keeps flood zip lists out of circular imports.
"""

from __future__ import annotations

# Elevated / special-case buffers (Town 'N' Country / Rocky Point)
ELEVATED_FLOOD_ZIPS = {
    "33615": 8500.0,  # Sweetwater Creek / Old Tampa Bay — insurance is no joke
}

HIGH_FLOOD_ZIPS = {
    # South Tampa / Downtown
    "33602",
    "33606",
    "33611",
    "33616",
    "33629",
    # Tarpon / Dunedin / St. Pete core
    "34689",
    "34698",
    "33701",
    "33702",
    "33715",
    # Island / Beach communities
    "33706",
    "33707",
    "33708",
    "33767",
}

MODERATE_FLOOD_ZIPS = {
    # Riverview / Apollo Beach
    "33569",
    "33570",
    "33572",
}

FLOOD_ZIPS = HIGH_FLOOD_ZIPS | MODERATE_FLOOD_ZIPS | set(ELEVATED_FLOOD_ZIPS.keys())

DEFAULT_CLOSING_COST_PCT = 0.03
FL_DOC_STAMP_PER_100 = 0.70
MIN_WHOLESALE_FEE = 10000.0
FLOOD_BUFFER = 7500.0
MODERATE_FLOOD_BUFFER = 4000.0
MANUAL_FLOOD_MAO_HIT = 15000.0  # High Risk Flood Zone AE — 33615 "flood tax"
HIGH_RISK_FLOOD_HIT = 15000.0
MOLD_HUMIDITY_BUFFER_33615 = 5000.0  # extra AS-IS cushion for 33615 humidity/mold
