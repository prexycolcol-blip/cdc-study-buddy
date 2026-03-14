from __future__ import annotations

import json
import time
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


def format_duration(total_seconds: float) -> str:
    seconds = int(total_seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def start_timer() -> None:
    st.session_state.timer_running = True
    st.session_state.start_time = time.time()


def stop_and_save_timer() -> None:
    end_time = time.time()
    duration = end_time - st.session_state.start_time

    if duration < 1:
        st.warning("Study session was too short to save.")
        st.session_state.timer_running = False
        return

    session = {
        "start": datetime.fromtimestamp(st.session_state.start_time).strftime("%Y-%m-%d %H:%M:%S"),
        "end": datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": int(duration),
    }

    st.session_state.sessions.append(session)
    save_sessions(st.session_state.sessions)

    st.success(f"Session saved: {format_duration(duration)}")
    st.session_state.timer_running = False


def clear_sessions() -> None:
    st.session_state.sessions = []
    save_sessions([])


st.set_page_config(page_title="Study Timer", page_icon="⏳", layout="centered")
st.title("📚 CDC Study Tracker")
st.write("Track your focused study sessions and review your history.")

init_state()

st.subheader("Current Session")

if not st.session_state.timer_running:
    st.button("▶️ Start Study Timer", on_click=start_timer, use_container_width=True)
else:
    elapsed = time.time() - st.session_state.start_time
    st.metric("Elapsed Time", format_duration(elapsed))
    st.button("⏹️ Stop and Save Session", on_click=stop_and_save_timer, use_container_width=True)
    st.caption("Timer updates every second while running.")
    time.sleep(1)
    st.rerun()

st.divider()
st.subheader("Saved Sessions")

sessions = st.session_state.sessions
if sessions:
    total_seconds = sum(item["duration_seconds"] for item in sessions)
    st.metric("Total Study Time", format_duration(total_seconds))

    rows = [
        {
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
