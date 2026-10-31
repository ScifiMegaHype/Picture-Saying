# Picture Saying

A daily puzzle game: guess the saying, movie, song or celebrity name hidden in a single picture. It is Wordle crossed with a visual riddle, and the fastest solver tops the leaderboard. The riddles are heavily influenced by TheEzzShow (https://www.youtube.com/@TheEzzShow)

**Play it:** https://picture-saying.onrender.com/

## How the game works

Every day there is one new picture, and its pieces sound out the answer. A past puzzle shows the idea: four rain clouds, a big X and a pile of coins. Four-rain is "foreign", and X-change is "ex-change", so the answer was **Foreign exchange**. Sometimes, the colour scheme on the pictures matters. 

- Enter a name and press **Start Guessing**. The timer starts there and only stops when you get the saying right.
- There is no quitting and no pausing.
- Capital letters and punctuation do not matter.
- The fastest solving times for the day go on the leaderboard.

## The hints: colours for words

| Colour | Meaning |
| --- | --- |
| Green | The right word in the right place |
| Yellow | The word is in the saying, but in a different place |
| Orange-ish | Your word contains a word from the saying (the answer has "slip" and you type "slippery") |
| Grey | The word is not in the saying |

Two rules keep it fair:

- Each word in the answer can only be matched once, so duplicates are counted a single time.
- Only answer words of three or more letters can trigger orange, so a short word like "a" does not light up half your guess.

For the answer "Pink slip", the guess "pink slippery" shows **pink** in green and **slippery** in orange.

## How it is built

- **Vanilla**: HTML templates with plain CSS and JavaScript.
- **Flask** runs the server.
- **The server owns the clock.** The start time is recorded on the server when a player presses Start Guessing, and the final time is worked out there too. A player cannot fake a fast time, and a refresh simply resumes the real elapsed time.
- **Answers never reach the browser.** The page only receives the colour hints for each guess.
- **Neon** (serverless Postgres) stores the scores, and **Render** hosts the app behind **gunicorn**.
- **Puzzles are one line each.** A dictionary maps each date to an image and an answer, so adding tomorrow's puzzle means dropping in a picture and writing one line.
- **Preferences** a How To Play card before the game starts, and a setting, saved in the browser's `localStorage`, to hide the instructions on later visits.

### Project structure

```
Picture-Saying/
├── app.py              # Flask app, hint scoring, database access
├── templates/
│   └── index.html      # the page (HTML, CSS and JavaScript)
├── images/             # one puzzle picture per day
├── requirements.txt
├── .env                # local secrets (never committed)
└── .gitignore
```

### Routes

| Route | Method | Purpose |
| --- | --- | --- |
| `/` | GET | The game page |
| `/image` | GET | Today's picture |
| `/state` | GET | Whether the player has started or finished, so a refresh resumes the game |
| `/start` | POST | Starts the player's clock |
| `/guess` | POST | Scores a guess and returns the hints (saves the time on a correct answer) |
| `/leaderboard` | GET | Today's fastest times |

## Running it locally

You need Python 3 and a free [Neon](https://neon.tech) database.

1. Create and activate a virtual environment, then install the packages:

   ```powershell
   python -m venv venv
   venv\Scripts\activate
   python -m pip install -r requirements.txt
   ```

2. Create a `.env` file in the project folder. Use Neon's **pooled** connection string (the host contains `-pooler`):

   ```
   DATABASE_URL=postgresql://user:password@your-host-pooler.region.aws.neon.tech/neondb?sslmode=require
   SECRET_KEY=some-long-random-string
   ```

   Loading the file needs `python-dotenv` (`load_dotenv()` at the top of `app.py`). Alternatively, set the variables in your terminal before you run the app.

3. Start the app and open <http://127.0.0.1:5000>:

   ```powershell
   python app.py
   ```

The `scores` table is created automatically on startup.

## Adding a puzzle

1. Put the picture in `images/`.
2. Add one line to the `PUZZLES` dictionary in `app.py`, keyed by date:

   ```python
   PUZZLES = {
       "2026-11-01": {"image": "2026-11-01.png", "answer": "Piece of cake"},
   }
   ```

## Hiccups

Most of the lessons came from hosting, not from the game logic.

- **My leaderboard would have vanished.** I started with an SQLite leaderboard file, but the free tier on Render wipes its disk on every restart, redeploy and idle spin-down. Moving the day's scores to Neon fixed that.
- **Free servers fall asleep.** After about 15 minutes idle, the first request can take 50 seconds or more. It is fine for a hobby project, but players notice it. Anyone want to sposnor this one? $7/month 😁
- **Region matters.** Initially , the app was in Virginia and the database in Frankfurt, so every connection paid for a trip across the Atlantic. I moved the app to Frankfurt, which is closer to players in South Africa.

## Roadmap

- [ ] Sign in with Google, so a player's results follow them across devices
- [ ] Saved history: the day, time and number of guesses for every past attempt, with streaks
- [ ] Settings tied to the account instead of living in one browser

## Feedback

Give as much as you want
