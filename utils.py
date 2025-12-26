# utils.py
from datetime import datetime, timedelta, timezone
import os

TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "2"))
SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))

def has_active_access(user):
    if not user or not user.get("is_active", False):
        return False

    now = datetime.now(timezone.utc)

    if user.get("subscription_end"):
        subscription_end = datetime.fromisoformat(user["subscription_end"])
        return now <= subscription_end

    if user.get("trial_start"):
        trial_start = datetime.fromisoformat(user["trial_start"])
        trial_end = trial_start + timedelta(days=TRIAL_DAYS)
        return now <= trial_end

    return False

def days_left(user):
    if not user:
        return 0
    now = datetime.now(timezone.utc)
    if user.get("subscription_end"):
        subscription_end = datetime.fromisoformat(user["subscription_end"])
        diff = (subscription_end - now).days
        return max(0, diff)
    elif user.get("trial_start"):
        trial_start = datetime.fromisoformat(user["trial_start"])
        trial_end = trial_start + timedelta(days=TRIAL_DAYS)
        diff = (trial_end - now).days
        return max(0, diff)
    return 0
