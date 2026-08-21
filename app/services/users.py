"""
Handles everything related to a user's row in Supabase, keyed by phone number.
No sign-up flow: the first message from a new number auto-creates their row.
"""
from datetime import datetime
from app.db import supabase


def get_or_create_user(phone_number: str) -> dict:
    """Return the user's row, creating one if this is their first message."""
    result = supabase.table("users").select("*").eq("phone_number", phone_number).execute()
    if result.data:
        return result.data[0]

    new_user = {
        "phone_number": phone_number,
        "current_subject": None,
        "current_question_id": None,
        "questions_answered": 0,
        "correct_count": 0,
        "has_paid": False,
    }
    inserted = supabase.table("users").insert(new_user).execute()
    return inserted.data[0]


def update_user(phone_number: str, fields: dict) -> None:
    """Patch specific fields on a user's row (e.g. current_subject, score)."""
    fields["updated_at"] = datetime.utcnow().isoformat()
    supabase.table("users").update(fields).eq("phone_number", phone_number).execute()


def reset_progress(phone_number: str) -> None:
    """Used when a user picks a new subject — clears question pointer and running score."""
    update_user(phone_number, {
        "current_subject": None,
        "current_question_id": None,
        "questions_answered": 0,
        "correct_count": 0,
    })


def increment_score(phone_number: str, was_correct: bool, answered_so_far: int, correct_so_far: int) -> None:
    update_user(phone_number, {
        "questions_answered": answered_so_far + 1,
        "correct_count": correct_so_far + (1 if was_correct else 0),
    })


def has_access(user: dict, free_limit: int) -> bool:
    """True if the user has paid, or hasn't hit the free-preview limit yet."""
    if user.get("has_paid"):
        return True
    return (user.get("questions_answered") or 0) < free_limit
