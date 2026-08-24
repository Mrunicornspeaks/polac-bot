"""
Handles everything related to a user's row in Supabase, keyed by phone number.
No sign-up flow: the first message from a new number auto-creates their row.

Two separate sets of counters, kept deliberately independent:
  - questions_answered / correct_count  -> LIFETIME totals, never reset.
    These are what gate the free-question limit. Switching subjects or
    typing "menu" must NEVER touch these, or the paywall is trivially
    bypassed by picking a new subject every 10 questions.
  - session_answered / session_correct  -> resets every time a new
    practice session starts (new subject + question count chosen).
    Used only for the "session complete, you scored X/Y" summary.
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
        "last_answer": None,
        "questions_answered": 0,
        "correct_count": 0,
        "session_target": None,
        "session_answered": 0,
        "session_correct": 0,
        "has_paid": False,
    }
    inserted = supabase.table("users").insert(new_user).execute()
    return inserted.data[0]


def update_user(phone_number: str, fields: dict) -> None:
    """Patch specific fields on a user's row."""
    fields["updated_at"] = datetime.utcnow().isoformat()
    supabase.table("users").update(fields).eq("phone_number", phone_number).execute()


def start_new_session(phone_number: str, subject: str, target: int) -> None:
    """
    Called when a user picks a subject AND a question count.
    Resets ONLY session-level fields. Lifetime counters are untouched.
    """
    update_user(phone_number, {
        "current_subject": subject,
        "current_question_id": None,
        "last_answer": None,
        "session_target": target,
        "session_answered": 0,
        "session_correct": 0,
    })


def record_answer(phone_number: str, was_correct: bool, user: dict) -> dict:
    """
    Increments both lifetime and session counters after an answer.
    Returns the updated counts so the caller doesn't need a second read.
    """
    new_lifetime_answered = (user.get("questions_answered") or 0) + 1
    new_lifetime_correct = (user.get("correct_count") or 0) + (1 if was_correct else 0)
    new_session_answered = (user.get("session_answered") or 0) + 1
    new_session_correct = (user.get("session_correct") or 0) + (1 if was_correct else 0)

    update_user(phone_number, {
        "questions_answered": new_lifetime_answered,
        "correct_count": new_lifetime_correct,
        "session_answered": new_session_answered,
        "session_correct": new_session_correct,
    })

    return {
        "lifetime_answered": new_lifetime_answered,
        "lifetime_correct": new_lifetime_correct,
        "session_answered": new_session_answered,
        "session_correct": new_session_correct,
    }


def has_access(user: dict, free_limit: int) -> bool:
    """
    True if the user has paid, or hasn't hit the LIFETIME free-preview
    limit yet. This never resets on subject switch - that was the bug.
    """
    if user.get("has_paid"):
        return True
    return (user.get("questions_answered") or 0) < free_limit
