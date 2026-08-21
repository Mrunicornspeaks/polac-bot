"""
Everything to do with reading from the `questions` table.
"""
import random
from app.db import supabase


def list_subjects() -> list[str]:
    """Distinct subject names, alphabetically, for the menu."""
    result = supabase.table("questions").select("subject").execute()
    subjects = sorted({row["subject"] for row in result.data})
    return subjects


def get_random_question(subject: str, exclude_id: int | None = None) -> dict | None:
    """
    Pull one random question for a subject.
    exclude_id avoids immediately repeating the question just answered.
    """
    query = supabase.table("questions").select("*").eq("subject", subject)
    result = query.execute()
    pool = result.data
    if not pool:
        return None
    if exclude_id is not None and len(pool) > 1:
        pool = [q for q in pool if q["id"] != exclude_id]
    return random.choice(pool)


def get_question_by_id(question_id: int) -> dict | None:
    result = supabase.table("questions").select("*").eq("id", question_id).execute()
    return result.data[0] if result.data else None


def check_answer(question: dict, user_answer: str) -> bool:
    return user_answer.strip().upper() == question["correct_answer"].strip().upper()
