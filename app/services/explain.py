"""
Calls Groq to generate a short, conversational explanation of why the
correct answer is correct. Falls back to a plain message if the API call
fails, so a Groq outage never breaks the practice loop.

Explanations are generated ON DEMAND (when the user taps "View
explanation"), not automatically after every answer - this keeps the
chat from being flooded with AI text on every question, and means a
slow/failed Groq call never blocks the user from moving to the next
question.
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


async def generate_explanation(question: dict, user_answer: str | None = None) -> str:
    logger.debug(f"generate_explanation called. GROQ_API_KEY present: {bool(GROQ_API_KEY)}")
    
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set - using fallback explanation")
        return _fallback_explanation(question)

    correct_letter = question["correct_answer"].upper()
    correct_text = question[f"option_{correct_letter.lower()}"]

    user_answer_line = f"Student answered: {user_answer.upper()}\n" if user_answer else ""

    prompt = (
        f"Subject: {question['subject']}\n"
        f"Question: {question['question_text']}\n"
        f"Options: A) {question['option_a']}  B) {question['option_b']}  "
        f"C) {question['option_c']}  D) {question['option_d']}\n"
        f"Correct answer: {correct_letter}) {correct_text}\n"
        f"{user_answer_line}\n"
        "In 2-3 short sentences, explain why the correct answer is right, "
        "in plain, conversational language a student prepping for an exam "
        "would understand. Don't repeat the question back. No headers or lists."
    )

    try:
        logger.debug(f"Calling Groq API at {GROQ_URL}")
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
            explanation = data["choices"][0]["message"]["content"].strip()
            logger.info(f"Groq API succeeded. Explanation: {explanation}")
            return explanation
    except httpx.HTTPStatusError as e:
        logger.error(f"Groq API HTTP error: {e.status_code} - {e.response.text}")
        return _fallback_explanation(question)
    except httpx.TimeoutException:
        logger.error("Groq API timeout (15s exceeded)")
        return _fallback_explanation(question)
    except Exception as e:
        logger.error(f"Groq API failed: {type(e).__name__}: {str(e)}", exc_info=True)
        return _fallback_explanation(question)


def _fallback_explanation(question: dict) -> str:
    correct_letter = question["correct_answer"].upper()
    correct_text = question[f"option_{correct_letter.lower()}"]
    return f"The correct answer is {correct_letter}) {correct_text}."
