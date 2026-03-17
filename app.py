from __future__ import annotations

import base64
import json
import os
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

    if "last_flashcard" not in st.session_state:
        st.session_state.last_flashcard = None


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


def generate_flashcard_with_ai(image_bytes: bytes, topic: str, extra_context: str) -> tuple[str, str, str]:
    api_key = os.getenv("cdc")
    if not api_key:
        question = f"What are 3 key facts about {topic}?"
        answer = (
            "1) Define the core concept in one sentence.\\n"
            "2) List one real-world example.\\n"
            "3) Explain why it matters for exams and practical work."
        )
        note = "No OPENAI_API_KEY found, so a local fallback flashcard was generated."
        return question, answer, note

    encoded_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Create one concise study flashcard from this image. "
        "Return strict JSON with keys: question, answer. "
        f"Topic hint: {topic}. Additional context: {extra_context or 'None'}"
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
        question = f"What are 3 key facts about {topic}?"
        answer = "Could not reach AI service. Use your uploaded image as reference and summarize key points."
        return question, answer, f"AI request failed: {exc}"

    text_parts = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text_parts.append(content.get("text", ""))

    raw = "\n".join(text_parts).strip()
    try:
        data = json.loads(raw)
        question = data.get("question", f"What is important about {topic}?")
        answer = data.get("answer", "Review the image and summarize the key concepts.")
    except json.JSONDecodeError:
        question = f"What concept does this {topic} image represent?"
        answer = raw or "Review the uploaded image and write a summary in your own words."

    return question, answer, "AI-generated flashcard created successfully."


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
st.subheader("AI Flashcard from Your Picture")
st.caption("Upload an image of notes/slides. The app creates a study flashcard from it.")
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

if st.button("✨ Generate Flashcard", use_container_width=True):
if st.button("✨ Generate Flashcards", use_container_width=True):
    if uploaded_image is None:
        st.warning("Please upload an image first.")
    else:
        topic = flashcard_topic.strip() or "your study subject"
        image_bytes = uploaded_image.getvalue()
        with st.spinner("Generating flashcard..."):
            question, answer, note = generate_flashcard_with_ai(image_bytes, topic, flashcard_context.strip())

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
        st.markdown("### Flashcard")
        st.markdown(f"**Q:** {question}")
        st.markdown(f"**A:** {answer}")

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
