from flask import Flask, redirect, render_template, request
from transformers import pipeline
import sqlite3
import logging

app = Flask(__name__)

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------- MODEL ----------------
classifier = pipeline(
    "text-classification",
    model="unitary/toxic-bert"
)

# ---------------- POLICY ENGINE ----------------
def policy_engine(label, score):
    if label == "toxic" and score > 0.85:
        return "AUTO_REMOVE", 9
    elif label == "toxic" and score > 0.60:
        return "SEND_TO_MODERATOR", 6
    else:
        return "ALLOW", 2


# ---------------- DATABASE ----------------
def get_db_connection():
    return sqlite3.connect("database.db")


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT,
        label TEXT,
        confidence REAL,
        severity INTEGER,
        action TEXT
    )
    """)

    conn.commit()
    conn.close()


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return render_template("submit.html")


@app.route("/submit", methods=["POST"])
def submit():

    content = request.form.get("content")

    # ---------------- INPUT VALIDATION ----------------
    if not content or content.strip() == "":
        return "Content cannot be empty"

    if len(content) < 3:
        return "Content too short"

    if len(content) > 500:
        return "Content too long"

    # ---------------- MODEL PREDICTION ----------------
    result = classifier(content)[0]

    model_label = result.get("label", "safe")
    score = result.get("score", 0)

    # Convert label
    if model_label.lower() == "toxic" and score >= 0.5:
        label = "toxic"
    else:
        label = "safe"

    # ---------------- POLICY ----------------
    action, severity = policy_engine(label, score)

    # ---------------- LOGGING ----------------
    logging.info(f"Content: {content} | Label: {label} | Score: {score:.2f} | Action: {action}")

    # ---------------- DATABASE SAVE ----------------
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO posts (content, label, confidence, severity, action)
        VALUES (?, ?, ?, ?, ?)
    """, (content, label, score, severity, action))

    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        content=content,
        label=label,
        score=score,
        severity=severity,
        action=action
    )


@app.route("/update/<int:post_id>/<decision>")
def update(post_id, decision):

    conn = get_db_connection()
    cursor = conn.cursor()

    # Log moderator action
    logging.info(f"Moderator action on post {post_id}: {decision}")

    cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM posts")
    posts = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM posts")
    total_posts = cursor.fetchone()[0]

    # ---------------- NEW FEATURE ----------------
    cursor.execute("SELECT COUNT(*) FROM posts WHERE label='toxic'")
    toxic_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM posts WHERE label='safe'")
    safe_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        posts=posts,
        total_posts=total_posts,
        toxic_count=toxic_count,
        safe_count=safe_count
    )


# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)