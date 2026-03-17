from __future__ import annotations

import base64
import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import streamlit as st

DATA_FILE = Path("study_sessions.json")


def load_sessions() -> list[dict]:
    if not DATA_FILE.exists():
        return []

    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_sessions(sessions: list[dict]) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(sessions, file, indent=2)


def init_state() -> None:
    if "sessions" not in st.session_state:
        st.session_state.sessions = load_sessions()

    if "timer_running" not in st.session_state:
        st.session_state.timer_running = False

    if "start_time" not in st.session_state:
        st.session_state.start_time = 0.0

    if "current_subject" not in st.session_state:
        st.session_state.current_subject = ""

    if "latest_flashcards" not in st.session_state:
        st.session_state.latest_flashcards = []


def format_duration(total_seconds: float) -> str:
    seconds = int(total_seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def start_timer(subject: str) -> None:
    st.session_state.timer_running = True
    st.session_state.start_time = time.time()
    st.session_state.current_subject = subject.strip() or "General Study"


def stop_and_save_timer() -> None:
    end_time = time.time()
    duration = end_time - st.session_state.start_time

    if duration < 1:
        st.warning("Study session was too short to save.")
        st.session_state.timer_running = False
        st.session_state.current_subject = ""
        return

    session = {
        "subject": st.session_state.current_subject or "General Study",
        "start": datetime.fromtimestamp(st.session_state.start_time).strftime("%Y-%m-%d %H:%M:%S"),
        "end": datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": int(duration),
    }

    st.session_state.sessions.append(session)
    save_sessions(st.session_state.sessions)

    st.success(f"Session saved: {format_duration(duration)} for {session['subject']}")
    st.session_state.timer_running = False
    st.session_state.current_subject = ""


def clear_sessions() -> None:
    st.session_state.sessions = []
    save_sessions([])


def extract_json_text(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        if len(parts) >= 3:
            return parts[1].replace("json", "", 1).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def fallback_flashcards(topic: str, extra_context: str, count: int) -> list[dict]:
    context_note = extra_context or "the uploaded image"
    templates = [
        {
            "question": f"What is the core idea of {topic}?",
            "answer": f"Explain {topic} in one sentence using details from {context_note}.",
            "hint": "Focus on the definition first.",
        },
        {
            "question": f"Which example best represents {topic}?",
            "answer": "Give one practical example and explain why it matches the concept.",
            "hint": "Use a real-life or exam-style scenario.",
        },
        {
            "question": f"Why does {topic} matter for studying?",
            "answer": "Describe how this concept could appear in tests or practical use.",
            "hint": "Think impact, not just memorization.",
        },
        {
            "question": f"What common mistake do students make with {topic}?",
            "answer": "Name one misunderstanding and provide the correct explanation.",
            "hint": "Contrast wrong vs right understanding.",
        },
        {
            "question": f"How would you teach {topic} in 30 seconds?",
            "answer": "Summarize the concept quickly using simple words and one key detail.",
            "hint": "Use the Feynman technique.",
        },
    ]
    return templates[:count]


def generate_flashcards_with_ai(
    image_bytes: bytes,
    topic: str,
    extra_context: str,
    card_count: int,
    difficulty: str,
) -> tuple[list[dict], str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        cards = fallback_flashcards(topic, extra_context, card_count)
        return cards, "No OPENAI_API_KEY found, so fallback flashcards were generated locally."

    encoded_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        f"Create exactly {card_count} study flashcards from the image. "
        f"Difficulty: {difficulty}. Topic hint: {topic}. Additional context: {extra_context or 'None'}. "
        "Return strict JSON only in this format: "
        '{"flashcards":[{"question":"...","answer":"...","hint":"..."}]}. '
        "Keep answers concise and exam-focused."
    )

    payload = {
        "model": "gpt-4.1-mini",
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{encoded_image}",
                    },
                ],
            }
        ],
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response_json = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        cards = fallback_flashcards(topic, extra_context, card_count)
        return cards, f"AI request failed ({exc}); fallback flashcards were generated locally."

    text_parts = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text_parts.append(content.get("text", ""))

    parsed_text = extract_json_text("\n".join(text_parts))
    try:
        parsed = json.loads(parsed_text)
        cards = parsed.get("flashcards", [])
        cleaned_cards = []
        for card in cards:
            question = str(card.get("question", "")).strip()
            answer = str(card.get("answer", "")).strip()
            hint = str(card.get("hint", "")).strip()
            if question and answer:
                cleaned_cards.append({"question": question, "answer": answer, "hint": hint})

        if cleaned_cards:
            return cleaned_cards[:card_count], "AI-generated flashcards created successfully."
    except json.JSONDecodeError:
        pass

    cards = fallback_flashcards(topic, extra_context, card_count)
    return cards, "AI output was not valid JSON; fallback flashcards were generated locally."


st.set_page_config(page_title="Study Timer", page_icon="⏳", layout="centered")
st.title("📚 CDC Study Buddy")
st.write("Use a labeled study timer, review your latest session, and create flashcards from images.")

init_state()

st.subheader("Current Session")
subject_input = st.text_input("Study subject label", placeholder="Biology, Algebra, CDC prep...")
st.caption("Tip: give each session a clear subject so your history stays organized.")

if not st.session_state.timer_running:
    st.button(
        "▶️ Start Study Timer",
        on_click=start_timer,
        args=(subject_input,),
        use_container_width=True,
    )
else:
    elapsed = time.time() - st.session_state.start_time
    st.metric("Elapsed Time", format_duration(elapsed))
    st.caption(f"Subject: {st.session_state.current_subject}")
    st.button("⏹️ Stop and Save Session", on_click=stop_and_save_timer, use_container_width=True)
    st.caption("Timer updates every second while running.")
    time.sleep(1)
    st.rerun()

st.divider()
st.subheader("Last Study Session")

sessions = st.session_state.sessions
if sessions:
    last = sessions[-1]
    cols = st.columns(3)
    cols[0].metric("Subject", last.get("subject", "General Study"))
    cols[1].metric("Duration", format_duration(last["duration_seconds"]))
    cols[2].metric("Started", last["start"])
else:
    st.info("No sessions yet. Start a timer to create your first entry.")

st.divider()
st.subheader("Saved Sessions")

if sessions:
    total_seconds = sum(item["duration_seconds"] for item in sessions)
    st.metric("Total Study Time", format_duration(total_seconds))

    rows = [
        {
            "Subject": item.get("subject", "General Study"),
            "Start": item["start"],
            "End": item["end"],
            "Duration": format_duration(item["duration_seconds"]),
        }
        for item in reversed(sessions)
    ]
    st.dataframe(rows, use_container_width=True)
    st.button("🗑️ Clear Saved Sessions", on_click=clear_sessions)
else:
    st.info("No saved study sessions yet. Start the timer to log your first one!")

st.divider()
st.subheader("AI Flashcards from Your Picture")
st.caption("Upload notes/slides and generate multiple flashcards with hints.")

flashcard_topic = st.text_input("Flashcard topic", placeholder="Cell biology")
flashcard_context = st.text_area("Extra context (optional)", placeholder="What chapter or exam is this for?")
col1, col2 = st.columns(2)
flashcard_count = col1.slider("Number of flashcards", min_value=1, max_value=5, value=3)
difficulty = col2.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
uploaded_image = st.file_uploader("Upload a picture", type=["png", "jpg", "jpeg", "webp"])

if uploaded_image is not None:
    st.image(uploaded_image, caption="Uploaded study image", use_container_width=True)

if st.button("✨ Generate Flashcards", use_container_width=True):
    if uploaded_image is None:
        st.warning("Please upload an image first.")
    else:
        topic = flashcard_topic.strip() or "your study subject"
        image_bytes = uploaded_image.getvalue()
        with st.spinner("Generating flashcards..."):
            cards, note = generate_flashcards_with_ai(
                image_bytes=image_bytes,
                topic=topic,
                extra_context=flashcard_context.strip(),
                card_count=flashcard_count,
                difficulty=difficulty,
            )

        st.session_state.latest_flashcards = cards
        st.success(note)

if st.session_state.latest_flashcards:
    header_cols = st.columns([3, 1])
    header_cols[0].markdown("### Latest Flashcard Set")
    if header_cols[1].button("🔀 Shuffle"):
        random.shuffle(st.session_state.latest_flashcards)

    for index, card in enumerate(st.session_state.latest_flashcards, start=1):
        with st.expander(f"Card {index}: {card['question']}"):
            st.markdown(f"**Answer:** {card['answer']}")
            if card.get("hint"):
                st.caption(f"Hint: {card['hint']}")
