"""
The conversation loop. One function, handle_incoming_message, decides what
to do with every message a user sends, based on their current state in the
`users` table plus what they just said.

States are implicit, not a formal state machine:
  - no current_subject          -> show the subject menu
  - current_subject set         -> either answering a question, or typed
                                    "menu" / "next"
"""
import os
from app.services import users as users_svc
from app.services import questions as questions_svc
from app.services import whatsapp as wa
from app.services import explain as explain_svc
from app.services import payment as payment_svc

FREE_QUESTION_LIMIT = int(os.environ.get("FREE_QUESTION_LIMIT", "10"))


async def handle_incoming_message(msg: dict) -> None:
    phone = msg["from"]
    user = users_svc.get_or_create_user(phone)
    text = (msg.get("text") or "").strip()
    list_id = msg.get("list_id")

    # Global commands, available from anywhere in the flow
    if text.lower() in ("menu", "subjects", "restart") and not list_id:
        await send_subject_menu(phone)
        return

    if list_id and list_id.startswith("subject::"):
        subject = list_id.split("::", 1)[1]
        await start_subject(phone, user, subject)
        return

    if list_id and list_id.startswith("answer::"):
        letter = list_id.split("::", 1)[1]
        await handle_answer(phone, user, letter)
        return

    if text.lower() == "next":
        await send_next_question(phone, user)
        return

    if text.lower() in ("pay", "upgrade", "subscribe"):
        await send_payment_link(phone)
        return

    # First-ever message, or anything unrecognised -> show the menu
    if not user.get("current_subject"):
        await send_subject_menu(phone)
    else:
        await wa.send_text(
            phone,
            "Not sure what you mean. Type *next* for another question, "
            "or *menu* to switch subjects.",
        )


async def send_subject_menu(phone: str) -> None:
    subjects = questions_svc.list_subjects()
    rows = [
        {"id": f"subject::{s}", "title": s[:24]}
        for s in subjects[:10]  # WhatsApp list messages cap at 10 rows
    ]
    await wa.send_list(
        to=phone,
        header="POLAC Prep 🚔",
        body="Pick a subject to start practicing:",
        button_text="Choose subject",
        rows=rows,
    )


async def start_subject(phone: str, user: dict, subject: str) -> None:
    users_svc.reset_progress(phone)
    users_svc.update_user(phone, {"current_subject": subject})
    question = questions_svc.get_random_question(subject)
    if not question:
        await wa.send_text(phone, "No questions found for that subject yet — try another one.")
        await send_subject_menu(phone)
        return
    users_svc.update_user(phone, {"current_question_id": question["id"]})
    await send_question(phone, question)


async def send_next_question(phone: str, user: dict) -> None:
    subject = user.get("current_subject")
    if not subject:
        await send_subject_menu(phone)
        return

    if not users_svc.has_access(user, FREE_QUESTION_LIMIT):
        await send_payment_prompt(phone)
        return

    prev_id = user.get("current_question_id")
    question = questions_svc.get_random_question(subject, exclude_id=prev_id)
    if not question:
        await wa.send_text(phone, "That's all the questions I have for this subject right now!")
        return
    users_svc.update_user(phone, {"current_question_id": question["id"]})
    await send_question(phone, question)


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
        await send_subject_menu(phone)
        return

    question = questions_svc.get_question_by_id(question_id)
    if not question:
        await send_subject_menu(phone)
        return

    was_correct = questions_svc.check_answer(question, letter)
    answered_so_far = user.get("questions_answered") or 0
    correct_so_far = user.get("correct_count") or 0
    users_svc.increment_score(phone, was_correct, answered_so_far, correct_so_far)

    verdict = "✅ Correct!" if was_correct else "❌ Not quite."
    explanation = await explain_svc.generate_explanation(question, letter, was_correct)
    await wa.send_text(phone, f"{verdict}\n\n{explanation}")

    new_answered = answered_so_far + 1
    if new_answered % 10 == 0:
        new_correct = correct_so_far + (1 if was_correct else 0)
        await wa.send_text(phone, f"📊 Score so far: {new_correct}/{new_answered}")

    await send_next_question(phone, users_svc.get_or_create_user(phone))


async def send_payment_prompt(phone: str) -> None:
    price = os.environ.get("ACCESS_PRICE_NAIRA", "2000")
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
