"""
The conversation loop. handle_incoming_message decides what to do with
every message, based on the user's row in Supabase plus what they just
sent (either free text, or the id of a list row they tapped).

Conversation shape:
  subject menu (paginated) -> question-count menu -> question loop
  (answer -> verdict -> [view explanation] / continue) -> session
  complete summary -> repeat or new subject

Free-question gating uses LIFETIME counters only (users_svc.has_access),
which are never reset by picking a new subject or typing "menu" - that
was the original bug.
"""
import os
from app.services import users as users_svc
from app.services import questions as questions_svc
from app.services import whatsapp as wa
from app.services import explain as explain_svc
from app.services import payment as payment_svc

FREE_QUESTION_LIMIT = int(os.environ.get("FREE_QUESTION_LIMIT", "10"))
QUESTION_COUNT_OPTIONS = [10, 20, 25, 30]
SUBJECTS_PER_PAGE = 9  # leaves room for a "more subjects" row (10 max per WhatsApp list)


async def handle_incoming_message(msg: dict) -> None:
    phone = msg["from"]
    user = users_svc.get_or_create_user(phone)
    text = (msg.get("text") or "").strip()
    list_id = msg.get("list_id")

    # Global text commands
    if text.lower() in ("menu", "subjects", "restart") and not list_id:
        await send_subject_menu(phone, page=0)
        return

    if text.lower() == "next":
        await send_next_question(phone, users_svc.get_or_create_user(phone))
        return

    if text.lower() in ("pay", "upgrade", "subscribe"):
        await send_payment_link(phone)
        return

    # Interactive list taps
    if list_id:
        if list_id.startswith("subjpage::"):
            page = int(list_id.split("::", 1)[1])
            await send_subject_menu(phone, page=page)
            return

        if list_id.startswith("subject::"):
            subject = list_id.split("::", 1)[1]
            await choose_subject(phone, subject)
            return

        if list_id.startswith("count::"):
            count = int(list_id.split("::", 1)[1])
            await start_session(phone, count)
            return

        if list_id.startswith("answer::"):
            letter = list_id.split("::", 1)[1]
            await handle_answer(phone, user, letter)
            return

        if list_id == "explain::":
            await send_explanation(phone)
            return

        if list_id == "continue::":
            await send_next_question(phone, users_svc.get_or_create_user(phone))
            return

        if list_id == "repeat::":
            user = users_svc.get_or_create_user(phone)
            subject = user.get("current_subject")
            if subject:
                await send_count_menu(phone, subject)
            else:
                await send_subject_menu(phone, page=0)
            return

    # First-ever message, or anything unrecognised
    if not user.get("current_subject"):
        await send_subject_menu(phone, page=0)
    else:
        await wa.send_text(
            phone,
            "Not sure what you mean. Type *next* for another question, "
            "or *menu* to switch subjects.",
        )


# ---------------------------------------------------------------------------
# Subject menu (paginated to handle more than 10 subjects)
# ---------------------------------------------------------------------------

async def send_subject_menu(phone: str, page: int = 0) -> None:
    subjects = questions_svc.list_subjects()
    total = len(subjects)

    if total <= 10:
        chunk = subjects
        has_more = False
    else:
        start = page * SUBJECTS_PER_PAGE
        chunk = subjects[start:start + SUBJECTS_PER_PAGE]
        has_more = (start + SUBJECTS_PER_PAGE) < total

    rows = [{"id": f"subject::{s}", "title": s[:24]} for s in chunk]
    if has_more:
        rows.append({"id": f"subjpage::{page + 1}", "title": "➡️ More subjects"})

    header = "POLAC Prep 🚔" if total <= 10 else f"POLAC Prep 🚔 (Page {page + 1})"
    await wa.send_list(
        to=phone,
        header=header,
        body="Pick a subject to start practicing:",
        button_text="Choose subject",
        rows=rows,
    )


async def choose_subject(phone: str, subject: str) -> None:
    users_svc.update_user(phone, {"current_subject": subject})
    await send_count_menu(phone, subject)


async def send_count_menu(phone: str, subject: str) -> None:
    rows = [{"id": f"count::{n}", "title": f"{n} questions"} for n in QUESTION_COUNT_OPTIONS]
    await wa.send_list(
        to=phone,
        header=subject[:24],
        body="How many questions would you like to practice in this session?",
        button_text="Choose amount",
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

async def start_session(phone: str, count: int) -> None:
    user = users_svc.get_or_create_user(phone)
    subject = user.get("current_subject")
    if not subject:
        await send_subject_menu(phone, page=0)
        return

    users_svc.start_new_session(phone, subject, count)

    if not users_svc.has_access(user, FREE_QUESTION_LIMIT):
        await send_payment_prompt(phone)
        return

    question = questions_svc.get_random_question(subject)
    if not question:
        await wa.send_text(phone, "No questions found for that subject yet — try another one.")
        await send_subject_menu(phone, page=0)
        return
    users_svc.update_user(phone, {"current_question_id": question["id"]})
    await send_question(phone, question)


async def send_next_question(phone: str, user: dict) -> None:
    subject = user.get("current_subject")
    target = user.get("session_target")

    if not subject or not target:
        await send_subject_menu(phone, page=0)
        return

    if not users_svc.has_access(user, FREE_QUESTION_LIMIT):
        await send_payment_prompt(phone)
        return

    session_answered = user.get("session_answered") or 0
    if session_answered >= target:
        await send_session_complete(phone, user)
        return

    prev_id = user.get("current_question_id")
    question = questions_svc.get_random_question(subject, exclude_id=prev_id)
    if not question:
        await wa.send_text(phone, "That's all the questions I have for this subject right now!")
        return
    users_svc.update_user(phone, {"current_question_id": question["id"]})
    await send_question(phone, question)


async def send_session_complete(phone: str, user: dict) -> None:
    correct = user.get("session_correct") or 0
    target = user.get("session_target") or 0
    subject = user.get("current_subject") or ""

    rows = [
        {"id": "repeat::", "title": "🔁 Practice again"},
        {"id": "subjpage::0", "title": "📚 Choose new subject"},
    ]
    await wa.send_list(
        to=phone,
        header=subject[:24],
        body=f"🎉 Session complete! You scored {correct}/{target}.",
        button_text="What next?",
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Question + answer flow
# ---------------------------------------------------------------------------

async def send_question(phone: str, question: dict) -> None:
    body = (
        f"{question['question_text']}\n\n"
        f"A) {question['option_a']}\n"
        f"B) {question['option_b']}\n"
        f"C) {question['option_c']}\n"
        f"D) {question['option_d']}"
    )
    rows = [
        {"id": "answer::A", "title": "A", "description": question["option_a"][:60]},
        {"id": "answer::B", "title": "B", "description": question["option_b"][:60]},
        {"id": "answer::C", "title": "C", "description": question["option_c"][:60]},
        {"id": "answer::D", "title": "D", "description": question["option_d"][:60]},
    ]
    await wa.send_list(
        to=phone,
        header=question["subject"][:24],
        body=body[:1024],
        button_text="Select answer",
        rows=rows,
    )


async def handle_answer(phone: str, user: dict, letter: str) -> None:
    question_id = user.get("current_question_id")
    if not question_id:
        await send_subject_menu(phone, page=0)
        return

    question = questions_svc.get_question_by_id(question_id)
    if not question:
        await send_subject_menu(phone, page=0)
        return

    was_correct = questions_svc.check_answer(question, letter)
    users_svc.record_answer(phone, was_correct, user)
    users_svc.update_user(phone, {"last_answer": letter})

    correct_letter = question["correct_answer"].upper()
    correct_text = question[f"option_{correct_letter.lower()}"]

    if was_correct:
        verdict = "✅ Correct!"
    else:
        verdict = f"❌ Not quite. Correct answer: {correct_letter}) {correct_text}"
    await wa.send_text(phone, verdict)

    # Explanation is opt-in via a tap, not auto-generated - keeps chat
    # clean and means a slow/failed Groq call never blocks progress.
    rows = [
        {"id": "explain::", "title": "📖 View explanation"},
        {"id": "continue::", "title": "➡️ Continue"},
    ]
    await wa.send_list(
        to=phone,
        header=question["subject"][:24],
        body="Want to see why, or keep going?",
        button_text="Choose",
        rows=rows,
    )


async def send_explanation(phone: str) -> None:
    user = users_svc.get_or_create_user(phone)
    question_id = user.get("current_question_id")
    if not question_id:
        await send_subject_menu(phone, page=0)
        return

    question = questions_svc.get_question_by_id(question_id)
    if not question:
        await send_subject_menu(phone, page=0)
        return

    explanation = await explain_svc.generate_explanation(question, user.get("last_answer"))
    await wa.send_text(phone, explanation)

    rows = [{"id": "continue::", "title": "➡️ Continue"}]
    await wa.send_list(
        to=phone,
        header=question["subject"][:24],
        body="Ready for the next one?",
        button_text="Continue",
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

async def send_payment_prompt(phone: str) -> None:
    price = os.environ.get("ACCESS_PRICE_NAIRA", "1000")
    await wa.send_text(
        phone,
        f"You've used your {FREE_QUESTION_LIMIT} free practice questions! 🎉\n\n"
        f"Unlock unlimited practice across all subjects for ₦{price} "
        f"(one-time, valid through your exam window).\n\n"
        "Reply *PAY* to get your payment link.",
    )


async def send_payment_link(phone: str) -> None:
    link = await payment_svc.generate_payment_link(phone)
    if link:
        await wa.send_text(phone, f"Tap to pay securely:\n{link}\n\nOnce paid, you'll get full access instantly.")
    else:
        await wa.send_text(phone, "Sorry, something went wrong generating your payment link. Please try again shortly.")
