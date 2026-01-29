import os
import secrets
from datetime import datetime, timedelta

from flask import Flask, request, session, redirect, url_for, render_template_string, abort
import pandas as pd

APP_TITLE = "Random Quiz (20 of 100)"
QUESTION_BANK_FILE = "QUESTION_BANK.xlsx"  # app expects this name in the same folder
QUESTIONS_PER_QUIZ = 20

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# Load once at startup
df = pd.read_excel(QUESTION_BANK_FILE)

required_cols = {"QuestionID","QuestionText","OptionA","OptionB","OptionC","OptionD","CorrectAnswer"}
if not required_cols.issubset(set(df.columns)):
    missing = required_cols - set(df.columns)
    raise RuntimeError(f"Question bank missing columns: {missing}")

df["QuestionID"] = df["QuestionID"].astype(str)

PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 900px; margin: 30px auto; line-height: 1.35; }
    .q { padding: 12px 14px; border: 1px solid #ddd; border-radius: 10px; margin: 12px 0; }
    .meta { color: #555; font-size: 13px; }
    .btn { padding: 10px 16px; border: none; border-radius: 10px; cursor: pointer; }
    .btn-primary { background: #0b5fff; color: white; }
    .btn-secondary { background: #eee; }
    .score { font-size: 20px; }
    .small { color: #666; font-size: 12px; }
    .topbar { display:flex; justify-content: space-between; align-items:center; }
    .pill { background:#f5f5f5; padding: 5px 10px; border-radius: 999px; font-size: 12px; color:#444; }
  </style>
</head>
<body>
  <div class="topbar">
    <h2 style="margin:0">{{ title }}</h2>
    <span class="pill">Questions: {{ n }}</span>
  </div>
  <p class="small">This quiz is generated randomly. Your question set is fixed once the quiz starts.</p>

  {% if mode == 'quiz' %}
    <form method="post" action="{{ url_for('submit') }}">
      {% for q in questions %}
        <div class="q">
          <div><b>{{ loop.index }}. {{ q.QuestionText }}</b></div>
          {% if q.get('Category') or q.get('Difficulty') %}
            <div class="meta">
              {% if q.get('Category') %}Category: {{ q.Category }}{% endif %}
              {% if q.get('Difficulty') %}{% if q.get('Category') %} | {% endif %}Difficulty: {{ q.Difficulty }}{% endif %}
            </div>
          {% endif %}
          <div style="margin-top:8px">
            {% for opt in ['A','B','C','D'] %}
              <label style="display:block; margin: 6px 0;">
                <input type="radio" name="{{ q.QuestionID }}" value="{{ opt }}" required>
                <span><b>{{ opt }}.</b> {{ q['Option' + opt] }}</span>
              </label>
            {% endfor %}
          </div>
        </div>
      {% endfor %}
      <button class="btn btn-primary" type="submit">Submit</button>
    </form>
    <p class="small">If you refresh this page before submitting, you may keep the same set depending on your session cookie.</p>

  {% elif mode == 'result' %}
    <p class="score"><b>Your score:</b> {{ score }} / {{ n }}</p>
    <p class="small">Submitted at {{ submitted_at }}</p>

    <details style="margin-top:14px">
      <summary>Show review</summary>
      {% for item in review %}
        <div class="q">
          <div><b>{{ loop.index }}. {{ item['QuestionText'] }}</b></div>
          <div class="small">Your answer: {{ item['YourAnswer'] }} | Correct: {{ item['CorrectAnswer'] }}</div>
        </div>
      {% endfor %}
    </details>

    <p style="margin-top:16px">
      <a class="btn btn-secondary" href="{{ url_for('start_over') }}">Start a new quiz</a>
    </p>
  {% endif %}
</body>
</html>"""

def _pick_question_ids():
    sample = df.sample(QUESTIONS_PER_QUIZ, replace=False)
    return sample["QuestionID"].tolist()

def _get_questions_by_ids(qids):
    subset = df[df["QuestionID"].isin(qids)].copy()
    # Preserve original order
    subset["__order"] = subset["QuestionID"].apply(lambda x: qids.index(x))
    subset = subset.sort_values("__order").drop(columns=["__order"])
    return subset.to_dict(orient="records")

@app.get("/")
def home():
    # Create a fixed question set for this user session if not present
    if "qids" not in session:
        session["qids"] = _pick_question_ids()
        session["started_at"] = datetime.utcnow().isoformat()

    questions = _get_questions_by_ids(session["qids"])
    return render_template_string(PAGE, title=APP_TITLE, questions=questions, n=len(questions), mode="quiz")

@app.post("/submit")
def submit():
    if "qids" not in session:
        return redirect(url_for("home"))

    qids = session["qids"]
    questions = _get_questions_by_ids(qids)

    score = 0
    review = []
    for q in questions:
        qid = q["QuestionID"]
        your = request.form.get(qid)
        correct = q["CorrectAnswer"]
        if your == correct:
            score += 1
        review.append({
            "QuestionID": qid,
            "QuestionText": q["QuestionText"],
            "YourAnswer": your,
            "CorrectAnswer": correct
        })

    submitted_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Clear session so next visit can generate a new quiz
    session.pop("qids", None)
    session.pop("started_at", None)

    return render_template_string(PAGE, title=APP_TITLE, score=score, n=len(review), review=review,
                                  submitted_at=submitted_at, mode="result")

@app.get("/start-over")
def start_over():
    session.pop("qids", None)
    session.pop("started_at", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    # Run on all interfaces so it can be accessed on your network if firewall allows
    # For local-only, change host to 127.0.0.1
    app.run(host="0.0.0.0", port=5000, debug=True)