"""
Streamlit Cloud entry point.
Prefer Main file path: app.py
This file exists so either app.py or main.py works.
"""
from __future__ import annotations

# Importing app.py runs the full DealShark UI (top-level Streamlit calls).
import app as _dealshark_app  # noqa: F401
