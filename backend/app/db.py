import json
import sqlite3
import time
import uuid
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "interviews.db"

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            id TEXT PRIMARY KEY,
            position TEXT,
            difficulty TEXT,
            total INTEGER,
            current_index INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ongoing',
            questions TEXT,
            answers TEXT DEFAULT '[]',
            followups TEXT DEFAULT '[]',
            scores TEXT DEFAULT '[]',
            created_at REAL
        )
        """)

def create_session(position: str, difficulty: str, questions: list) -> str:
    sid = uuid.uuid4().hex[:12]
    with _conn() as c:
        c.execute(
            "INSERT INTO interviews VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (sid, position, difficulty, len(questions), 0, "ongoing",
             json.dumps(questions, ensure_ascii=False), "[]", "[]", "[]", time.time()),
        )
    return sid

def load_session(sid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM interviews WHERE id=?", (sid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for k in ("questions", "answers", "followups", "scores"):
            d[k] = json.loads(d[k] or "[]")
        return d

def save_progress(sid: str, current_index: int, answers: list, followups: list, scores: list, status: str = "ongoing"):
    with _conn() as c:
        c.execute(
            "UPDATE interviews SET current_index=?, answers=?, followups=?, scores=?, status=? WHERE id=?",
            (current_index, json.dumps(answers, ensure_ascii=False),
             json.dumps(followups, ensure_ascii=False),
             json.dumps(scores, ensure_ascii=False), status, sid),
        )


def save_questions(sid: str, questions: list):
    """持久化题库(含每题 followup_count),否则追问上限只活在内存里,重启/多进程就丢。"""
    with _conn() as c:
        c.execute("UPDATE interviews SET questions=? WHERE id=?",
                  (json.dumps(questions, ensure_ascii=False), sid))
