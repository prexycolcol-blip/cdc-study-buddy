from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

DATA_FILE = Path("study_data.json")
POMODORO_FOCUS_MIN = 25
POMODORO_BREAK_MIN = 5


def default_store() -> dict:
    return {
        "sessions": [],
        "subjects": [],
        "tasks": [],
        "plans": {},
        "flashcards": [],
    }


def load_store() -> dict:
    if not DATA_FILE.exists():
        return default_store()

    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    base = default_store()
    base.update(data)
    return base


def save_store() -> None:
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(st.session_state.store, file, indent=2)


def init_state() -> None:
    if "store" not in st.session_state:
        st.session_state.store = load_store()

    if "timer_running" not in st.session_state:
        st.session_state.timer_running = False

    if "phase" not in st.session_state:
        st.session_state.phase = "Focus"

    if "phase_end" not in st.session_state:
        st.session_state.phase_end = None


def format_seconds(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def ensure_subject(name: str) -> None:
    if name and name not in st.session_state.store["subjects"]:
        st.session_state.store["subjects"].append(name)
        st.session_state.store["subjects"].sort()
        save_store()


def add_task(subject: str, task_name: str) -> None:
    if not subject or not task_name:
        return
    st.session_state.store["tasks"].append(
        {
            "id": int(time.time() * 1000),
            "subject": subject,
            "name": task_name,
            "done": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    save_store()


def record_session(duration_minutes: int, completed: bool = True) -> None:
    start_time = datetime.now() - timedelta(minutes=duration_minutes)
    st.session_state.store["sessions"].append(
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "start": start_time.strftime("%Y-%m-%d %H:%M"),
            "end": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "minutes": duration_minutes,
            "completed": completed,
            "phase": st.session_state.phase,
        }
    )
    save_store()


def start_pomodoro() -> None:
    st.session_state.timer_running = True
    st.session_state.phase = "Focus"
    st.session_state.phase_end = datetime.now() + timedelta(minutes=POMODORO_FOCUS_MIN)


def stop_pomodoro() -> None:
    st.session_state.timer_running = False
    st.session_state.phase_end = None


def tick_timer() -> None:
    if not st.session_state.timer_running or not st.session_state.phase_end:
        return

    remaining = int((st.session_state.phase_end - datetime.now()).total_seconds())
    if remaining > 0:
        return

    if st.session_state.phase == "Focus":
        record_session(POMODORO_FOCUS_MIN, completed=True)
        st.toast("✅ Focus session complete! Time for a 5-minute break.")
        st.session_state.phase = "Break"
        st.session_state.phase_end = datetime.now() + timedelta(minutes=POMODORO_BREAK_MIN)
    else:
        st.toast("🔔 Break over! Start your next focus session.")
        st.session_state.phase = "Focus"
        st.session_state.phase_end = datetime.now() + timedelta(minutes=POMODORO_FOCUS_MIN)


def mark_task(task_id: int, done: bool) -> None:
    for task in st.session_state.store["tasks"]:
        if task["id"] == task_id:
            task["done"] = done
            break
    save_store()


def get_study_minutes_for_period(days: int) -> int:
    cutoff = date.today() - timedelta(days=days - 1)
    total = 0
    for item in st.session_state.store["sessions"]:
        item_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
        if item_date >= cutoff:
            total += item["minutes"]
    return total


def set_plan(key: str, text: str) -> None:
    st.session_state.store["plans"][key] = text
    save_store()


def add_flashcard(subject: str, question: str, answer: str) -> None:
    if not question or not answer:
        return
    st.session_state.store["flashcards"].append(
        {
            "id": int(time.time() * 1000),
            "subject": subject or "General",
            "question": question,
            "answer": answer,
        }
    )
    save_store()


def delete_flashcard(card_id: int) -> None:
    st.session_state.store["flashcards"] = [
        card for card in st.session_state.store["flashcards"] if card["id"] != card_id
    ]
    save_store()


st.set_page_config(page_title="Study Buddy", page_icon="📚", layout="wide")
init_state()
tick_timer()

st.title("📚 Study Buddy Dashboard")
st.caption("Plan your study, run Pomodoro sessions, manage tasks, and track your progress.")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Today's Study", f"{get_study_minutes_for_period(1) / 60:.1f} h")
with col2:
    st.metric("This Week", f"{get_study_minutes_for_period(7) / 60:.1f} h")
with col3:
    tasks = st.session_state.store["tasks"]
    done_count = sum(1 for t in tasks if t["done"])
    completion = (done_count / len(tasks) * 100) if tasks else 0
    st.metric("Task Completion", f"{completion:.0f}%")

calendar_tab, timer_tab, task_tab, flashcard_tab, progress_tab = st.tabs(
    [
        "📅 Study Calendar",
        "⏱️ Pomodoro Timer",
        "✅ Task / Subject Tracker",
        "🗂️ Flashcards",
        "📊 Progress",
    ]
)

with calendar_tab:
    st.subheader("Daily / Weekly / Monthly Plans")
    cal1, cal2, cal3 = st.columns(3)
    with cal1:
        daily = st.text_area("Daily Plan", value=st.session_state.store["plans"].get("daily", ""), height=180)
        if st.button("Save Daily Plan"):
            set_plan("daily", daily)
            st.success("Daily plan saved")
    with cal2:
        weekly = st.text_area("Weekly Plan", value=st.session_state.store["plans"].get("weekly", ""), height=180)
        if st.button("Save Weekly Plan"):
            set_plan("weekly", weekly)
            st.success("Weekly plan saved")
    with cal3:
        monthly = st.text_area("Monthly Plan", value=st.session_state.store["plans"].get("monthly", ""), height=180)
        if st.button("Save Monthly Plan"):
            set_plan("monthly", monthly)
            st.success("Monthly plan saved")

    st.markdown("### Mark Completed Sessions")
    if st.button("➕ Add Completed 25-min Session"):
        record_session(POMODORO_FOCUS_MIN, completed=True)
        st.success("Completed focus session added")

with timer_tab:
    st.subheader("Pomodoro: 25 min Focus + 5 min Break")

    if st.session_state.timer_running and st.session_state.phase_end:
        seconds_left = int((st.session_state.phase_end - datetime.now()).total_seconds())
        st.metric(f"Current Phase: {st.session_state.phase}", format_seconds(seconds_left))
        st.progress(min(max(seconds_left, 0), (POMODORO_FOCUS_MIN if st.session_state.phase == "Focus" else POMODORO_BREAK_MIN) * 60) / ((POMODORO_FOCUS_MIN if st.session_state.phase == "Focus" else POMODORO_BREAK_MIN) * 60))
        c1, c2 = st.columns(2)
        with c1:
            if st.button("⏹️ Stop Timer", use_container_width=True):
                stop_pomodoro()
        with c2:
            if st.button("✅ Complete Focus Now", use_container_width=True):
                if st.session_state.phase == "Focus":
                    record_session(POMODORO_FOCUS_MIN, completed=True)
                    st.success("Focus session marked complete")
                stop_pomodoro()
        time.sleep(1)
        st.rerun()
    else:
        st.info("Timer is stopped.")
        if st.button("▶️ Start Pomodoro", use_container_width=True):
            start_pomodoro()
            st.rerun()

with task_tab:
    st.subheader("Subjects")
    with st.form("subject_form", clear_on_submit=True):
        subject_name = st.text_input("Add Subject (e.g., Math, Science)")
        add_subject_btn = st.form_submit_button("Add Subject")
        if add_subject_btn:
            if subject_name.strip():
                ensure_subject(subject_name.strip())
                st.success("Subject added")
            else:
                st.warning("Please enter a subject name")

    st.write("Current subjects:", ", ".join(st.session_state.store["subjects"]) if st.session_state.store["subjects"] else "None")

    st.subheader("Tasks")
    with st.form("task_form", clear_on_submit=True):
        subject_for_task = st.selectbox("Subject", options=st.session_state.store["subjects"] or ["General"])
        task_name = st.text_input("Task")
        add_task_btn = st.form_submit_button("Add Task")
        if add_task_btn:
            add_task(subject_for_task, task_name.strip())
            st.success("Task added")

    for task in st.session_state.store["tasks"]:
        new_val = st.checkbox(
            f"[{task['subject']}] {task['name']}",
            value=task["done"],
            key=f"task_{task['id']}",
        )
        if new_val != task["done"]:
            mark_task(task["id"], new_val)

with flashcard_tab:
    st.subheader("Manual Flashcards (No AI)")
    st.caption("Create and review your own flashcards only — no auto generation.")

    with st.form("flashcard_form", clear_on_submit=True):
        flash_subject = st.selectbox(
            "Subject",
            options=st.session_state.store["subjects"] or ["General"],
            key="flash_subject",
        )
        flash_question = st.text_input("Question", placeholder="What is photosynthesis?")
        flash_answer = st.text_area("Answer", placeholder="Process plants use to make food...")
        add_flash_btn = st.form_submit_button("Add Flashcard")
        if add_flash_btn:
            add_flashcard(flash_subject, flash_question.strip(), flash_answer.strip())
            st.success("Flashcard added")

    cards = st.session_state.store["flashcards"]
    if not cards:
        st.info("No flashcards yet. Add your first one above.")
    else:
        st.markdown("### Review Cards")
        for card in reversed(cards):
            with st.container(border=True):
                st.write(f"**[{card['subject']}]** {card['question']}")
                with st.expander("Show answer"):
                    st.write(card["answer"])
                if st.button("Delete", key=f"del_card_{card['id']}"):
                    delete_flashcard(card["id"])
                    st.rerun()

with progress_tab:
    st.subheader("Study Progress")
    today_minutes = get_study_minutes_for_period(1)
    week_minutes = get_study_minutes_for_period(7)
    month_minutes = get_study_minutes_for_period(30)

    p1, p2, p3 = st.columns(3)
    p1.metric("Today", f"{today_minutes / 60:.2f} h")
    p2.metric("This Week", f"{week_minutes / 60:.2f} h")
    p3.metric("This Month", f"{month_minutes / 60:.2f} h")

    tasks = st.session_state.store["tasks"]
    completed = sum(1 for t in tasks if t["done"])
    total = len(tasks)
    pct = (completed / total) if total else 0
    st.write(f"Task completion: **{completed}/{total} ({pct * 100:.0f}%)**")
    st.progress(pct)

    st.markdown("### Session History")
    if st.session_state.store["sessions"]:
        st.dataframe(list(reversed(st.session_state.store["sessions"])), use_container_width=True)
    else:
        st.info("No sessions recorded yet")
