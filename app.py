import os
import re
import time
from collections import Counter
from random import randint
from datetime import date

import psycopg
from psycopg.rows import dict_row
from flask import Flask, jsonify, render_template, request, send_from_directory, session

# When running locally
# from dotenv import load_dotenv
# load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
DATABASE_URL = os.environ["DATABASE_URL"]  # Neon connection string
IMAGE_DIR = "images"
LEADERBOARD_SIZE = 10

# One entry per day. Key = YYYY-MM-DD. Answer stays on the server only.
PUZZLES = { # Server date is used
    "2026-10-29": {"image": "2026-10-29.png", "answer": "Foreign Exchange"},
    "2026-10-30": {"image": "2026-10-30.png", "answer": "Pink Slip"},
    "2026-10-31": {"image": "2026-10-31.png", "answer": "Ice breaker"},
    "2026-11-01": {"image": "2026-11-01.png", "answer": "Forget"},
    "2026-11-02": {"image": "2026-11-02.png", "answer": "Step father"},
    "2026-11-03": {"image": "2026-11-03.png", "answer": "Try to understand"},
    "2026-11-04": {"image": "2026-11-04.png", "answer": "Top secret"},
    "2026-11-05": {"image": "2026-11-05.png", "answer": "Plot Twist"},
    "2026-11-06": {"image": "2026-11-06.png", "answer": "Internet Explorer"},
}
FALLBACK_DATE = "2026-10-29"  # used if today has no puzzle yet
# -------------------------------------------------------------------------

CORRECT = "ok"          # green
PRESENT = "present"     # yellow
CONTAINS = "contains"   # orange
ABSENT = "absent"       # grey
MIN_CONTAINED_LENGTH = 3  # ignore tiny answer words like "a" or "is"

app = Flask(__name__)
app.secret_key = SECRET_KEY

def get_db():
    """Open a Neon connection. Use `with get_db() as db:` - it commits and closes on exit."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row) # type: ignore

def init_db():
    with get_db() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS scores (
                   id SERIAL PRIMARY KEY,
                   puzzle_date TEXT NOT NULL,
                   name TEXT NOT NULL,
                   seconds REAL NOT NULL,
                   guesses INTEGER NOT NULL,
                   created_at TIMESTAMPTZ DEFAULT NOW()
               )"""
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS scores_date_seconds ON scores (puzzle_date, seconds)"
        )

def today_key():
    key = date.today().isoformat()
    return key if key in PUZZLES else FALLBACK_DATE

def normalize(text):
    """Case-insensitive, ignores punctuation and extra spaces."""
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()

def score_guess(guess_words, answer_words):
    hints = [ABSENT] * len(guess_words)
    remaining = Counter()

    # Pass 1: exact position matches (green); count unmatched answer words
    for i, answer_word in enumerate(answer_words):
        if i < len(guess_words) and guess_words[i] == answer_word:
            hints[i] = CORRECT
        else:
            remaining[answer_word] += 1

    # Pass 2: right word, wrong place (yellow), limited by remaining count
    for i, guess_word in enumerate(guess_words):
        if hints[i] == CORRECT:
            continue
        if remaining[guess_word] > 0:
            hints[i] = PRESENT
            remaining[guess_word] -= 1

    # Pass 3: guess word contains an unmatched answer word (orange)
    for i, guess_word in enumerate(guess_words):
        if hints[i] != ABSENT:
            continue
        for answer_word in remaining:
            if (
                remaining[answer_word] > 0
                and len(answer_word) >= MIN_CONTAINED_LENGTH
                and answer_word in guess_word
            ):
                hints[i] = CONTAINS
                remaining[answer_word] -= 1
                break

    return hints

@app.route("/")
def index():
    return render_template("index.html", word_count=len(PUZZLES[today_key()]["answer"].split()))

@app.route("/health")
def health():
    return "ok"

@app.route("/image")
def image():
    return send_from_directory(IMAGE_DIR, PUZZLES[today_key()]["image"])

@app.route("/state")
def state():
    key = today_key()
    start_time = session.get("start_" + key)
    return jsonify(
        started=start_time is not None,
        done=bool(session.get("done_" + key)),
        name=session.get("name", ""),
        elapsed=(time.time() - start_time) if start_time else 0,
    )

@app.route("/start", methods=["POST"])
def start():
    key = today_key()
    name = (request.json or {}).get("name", "").strip()[:20]
    if not name:
        return jsonify(error="Enter a name first"), 400
    if session.get("done_" + key):
        return jsonify(error="You already finished today's puzzle"), 400
    session["name"] = name

    session.setdefault("start_" + key, time.time())
    session["guesses_" + key] = session.get("guesses_" + key, 0)
    elapsed = time.time() - session["start_" + key]
    return jsonify(ok=True, elapsed=elapsed, word_count=len(PUZZLES[today_key()]["answer"].split()))

@app.route("/guess", methods=["POST"])
def guess():
    key = today_key()
    start_time = session.get("start_" + key)
    if start_time is None:
        return jsonify(error="Press Start first"), 400
    if session.get("done_" + key):
        return jsonify(error="Already finished"), 400

    guess_text = (request.json or {}).get("guess", "")
    answer_words = normalize(PUZZLES[key]["answer"]).split()
    guess_words = normalize(guess_text).split()

    session["guesses_" + key] += 1

    if guess_words == answer_words:
        seconds = round(time.time() - start_time, 2)
        session["done_" + key] = True
        with get_db() as db:
            db.execute(
                "INSERT INTO scores (puzzle_date, name, seconds, guesses) VALUES (%s, %s, %s, %s)",
                (key, str(session["name"])+str(randint(9999, 99999)), seconds, session["guesses_" + key]),
            )
        return jsonify(correct=True, seconds=seconds, guesses=session["guesses_" + key])

    # Wordle-style hint: which word positions are right
    hints = score_guess(guess_words, answer_words)
    return jsonify(correct=False, hints=hints, words=guess_words)

@app.route("/leaderboard")
def leaderboard():
    key = today_key()
    with get_db() as db:
        rows = db.execute(
            "SELECT name, seconds, guesses FROM scores WHERE puzzle_date = %s "
            "ORDER BY seconds ASC, guesses ASC LIMIT %s",
            (key, LEADERBOARD_SIZE),
        ).fetchall()
    return jsonify(rows)

init_db()

if __name__ == "__main__":
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=True)