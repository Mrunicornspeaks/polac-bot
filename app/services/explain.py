"""
Calls Groq to generate a short, conversational explanation of why the
correct answer is correct. Falls back to a plain message if the API call
fails, so a Groq outage never breaks the practice loop.
"""
import os
import httpx

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"  # fast + cheap, good enough for short explanations


async def generate_explanation(question: dict, user_answer: str, was_correct: bool) -> str:
    if not GROQ_API_KEY:
        return _fallback_explanation(question)

    correct_letter = question["correct_answer"].upper()
    correct_text = question[f"option_{correct_letter.lower()}"]

    prompt = (
        f"Subject: {question['subject']}\n"
        f"Question: {question['question_text']}\n"
        f"Options: A) {question['option_a']}  B) {question['option_b']}  "
        f"C) {question['option_c']}  D) {question['option_d']}\n"
        f"Correct answer: {correct_letter}) {correct_text}\n"
        f"Student answered: {user_answer.upper()}\n\n"
        "In 2-3 short sentences, explain why the correct answer is right, "
        "in plain, conversational language a student prepping for an exam "
        "would understand. Don't repeat the question back. No headers or lists."
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.4,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return _fallback_explanation(question)


def _fallback_explanation(question: dict) -> str:
    correct_letter = question["correct_answer"].upper()
    correct_text = question[f"option_{correct_letter.lower()}"]
    return f"The correct answer is {correct_letter}) {correct_text}."
