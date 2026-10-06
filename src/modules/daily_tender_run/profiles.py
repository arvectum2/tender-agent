from __future__ import annotations

import json
from pathlib import Path

from src.modules.daily_tender_run.schemas import DailyTenderProfile

_PROFILE_DIR = Path(__file__).resolve().parents[3] / "config" / "daily_tender_profiles"


def load_daily_tender_profile(profile_id: str) -> DailyTenderProfile:
    normalized = str(profile_id or "").strip()
    if not normalized:
        raise ValueError("profile_id is required")
    path = _PROFILE_DIR / f"{normalized}.json"
    if not path.is_file():
        raise ValueError(f"Unknown Daily Tender profile: {normalized}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    profile = DailyTenderProfile.model_validate(payload)
    if profile.profile_id != normalized:
        raise ValueError(
            f"Daily Tender profile identity mismatch: expected {normalized}, got {profile.profile_id}"
        )
    return profile
