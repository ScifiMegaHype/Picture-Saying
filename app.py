import os
import re
import time
from collections import Counter
from random import randint
from datetime import date

import psycopg
from psycopg.rows import dict_row
from flask import Flask, jsonify, render_template_string, request, send_from_directory, session

# When running locally
# from dotenv import load_dotenv
# load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
DATABASE_URL = os.environ["DATABASE_URL"]  # Neon connection string
IMAGE_DIR = "images"
LEADERBOARD_SIZE = 10
TIMEZONE_NOTE = "Puzzle date uses the server's local date."

# One entry per day. Key = YYYY-MM-DD. Answer stays on the server only.
PUZZLES = {
    "2026-10-29": {"image": "2026-10-29.png", "answer": "Foreign Exchange"},
    "2026-10-30": {"image": "2026-10-30.png", "answer": "Pink Slip"},
    "2026-10-31": {"image": "2026-10-31.png", "answer": "Ice breaker"},
    "2026-11-01": {"image": "2026-10-30.png", "answer": "Forget"},
    "2026-11-02": {"image": "2026-10-30.png", "answer": "Step father"},
    "2026-11-03": {"image": "2026-10-30.png", "answer": "Try to understand"},
    "2026-11-04": {"image": "2026-10-30.png", "answer": "Top secret"},
    "2026-11-05": {"image": "2026-10-30.png", "answer": "Plot Twist"},
    "2026-11-06": {"image": "2026-10-30.png", "answer": "Internet Explorer"},
}
FALLBACK_DATE = "2026-10-29"  # used if today has no puzzle yet
# -------------------------------------------------------------------------

CORRECT = "ok"
PRESENT = "present"
ABSENT = "absent"

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

    return hints

@app.route("/")
def index():
    return render_template_string(PAGE, word_count=len(PUZZLES[today_key()]["answer"].split()))

@app.route("/image")
def image():
    return send_from_directory(IMAGE_DIR, PUZZLES[today_key()]["image"])

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
            "ORDER BY seconds ASC LIMIT %s",
            (key, LEADERBOARD_SIZE),
        ).fetchall()
    return jsonify(rows)

PAGE = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Picture Saying</title>
<style>
  body{font-family:system-ui;max-width:480px;margin:0 auto;padding:16px;text-align:center}
  img{width:100%;border-radius:12px;display:none}
  input,button{font-size:1rem;padding:10px;margin:4px 0;width:100%;box-sizing:border-box}
  .row{display:flex;gap:4px;justify-content:center;margin:4px 0}
  .w{padding:4px 8px;border-radius:6px;background:#ccc}
  .w.ok{background:#6aaa64;color:#fff}
  .w.present{background:#c9b458;color:#fff}
  #timer{font-size:1.6rem;margin:8px 0}
  table{width:100%;border-collapse:collapse} td,th{padding:4px;border-bottom:1px solid #ddd}
</style>
<h2>Picture Saying</h2>
<div id="setup">
  <input id="name" placeholder="Your name" maxlength="20">
  <button onclick="startGame()">Start</button>
</div>
<div id="timer"></div>
<img id="pic" src="/image">
<div id="play" style="display:none">
  <p>{{ word_count }} words</p>
  <input id="guess" placeholder="Type the saying" onkeydown="if(event.key==='Enter')sendGuess()">
  <button onclick="sendGuess()">Guess</button>
  <div id="history"></div>
</div>
<h3>Today's leaderboard</h3>
<table id="board"></table>

<script>
let startMs = null, ticker = null;
const $ = id => document.getElementById(id);

async function post(url, body){
  const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return r.json();
}
function tick(){ $('timer').textContent = ((Date.now()-startMs)/1000).toFixed(1)+'s'; }

async function startGame(){
  const data = await post('/start',{name:$('name').value});
  if(data.error){ alert(data.error); return; }
  startMs = Date.now() - data.elapsed*1000;   // resume if page refreshed
  ticker = setInterval(tick, 100);
  $('setup').style.display='none'; $('pic').style.display='block'; $('play').style.display='block';
}
async function sendGuess(){
  const g = $('guess').value; if(!g.trim()) return;
  const data = await post('/guess',{guess:g});
  if(data.error){ alert(data.error); return; }
  if(data.correct){
    clearInterval(ticker);
    $('timer').textContent = 'Solved in '+data.seconds+'s ('+data.guesses+' guesses)';
    $('play').style.display='none'; loadBoard(); return;
  }
  const row = document.createElement('div'); row.className='row';
  data.words.forEach((w,i)=>{
    const s=document.createElement('span');
    s.className='w ' + data.hints[i];
    s.textContent=w; row.appendChild(s);
  });
  $('history').prepend(row); $('guess').value='';
}
function formatTime(totalSeconds) {
  const total = Math.round(totalSeconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;

  const pad = n => String(n).padStart(2, '0');
  return `${pad(hours)}h ${pad(minutes)}min ${pad(seconds)}s`;
}

async function loadBoard(){
  const rows = await (await fetch('/leaderboard')).json();
  $('board').innerHTML = '<tr><th>#</th><th>Name</th><th>Time</th><th>Guesses</th></tr>' +
    rows.map((r,i)=>`<tr><td>${i+1}</td><td>${r.name}</td><td>${formatTime(r.seconds)}</td><td>${r.guesses}</td></tr>`).join('');
}
loadBoard();
</script>
"""

init_db()

if __name__ == "__main__":
    app.run(debug=True)