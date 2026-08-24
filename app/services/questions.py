"""
Everything to do with reading from the `questions` table.
"""
import random
from app.db import supabase


def list_subjects() -> list[str]:
    """
    Distinct subject names, alphabetically, for the menu.
    Explicitly paginates through the full table - Supabase caps a single
    query at 1000 rows by default, which would silently miss subjects
    that only appear later in the table if we only made one request.
    """
    all_subjects = set()
    page_size = 1000
    start = 0
    while True:
        result = (
            supabase.table("questions")
            .select("subject")
            .range(start, start + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_subjects.update(row["subject"] for row in result.data)
        if len(result.data) < page_size:
            break
        start += page_size
    return sorted(all_subjects)


def get_random_question(subject: str, exclude_id: int | None = None) -> dict | None:
    """
    Pull one random question for a subject.
    exclude_id avoids immediately repeating the question just answered.
    Also paginated for the same reason as list_subjects.
    """
    pool = []
    page_size = 1000
    start = 0
    while True:
        result = (
            supabase.table("questions")
            .select("*")
            .eq("subject", subject)
            .range(start, start + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        pool.extend(result.data)
        if len(result.data) < page_size:
            break
        start += page_size

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
