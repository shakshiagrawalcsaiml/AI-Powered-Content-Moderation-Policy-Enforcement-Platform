from flask import Flask, redirect, render_template, request
from transformers import pipeline
import sqlite3

app = Flask(__name__)

# Load AI moderation model
classifier = pipeline(
    "text-classification",
    model="unitary/toxic-bert"
)

# Policy decision engine
def policy_engine(label, score):
    if label == "toxic" and score > 0.85:
        return "AUTO_REMOVE", 9
    elif label == "toxic" and score > 0.60:
        return "SEND_TO_MODERATOR", 6
    else:
        return "ALLOW", 2


# Initialize database
def init_db():
    conn = sqlite3.connect("database.db")
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


# Home page
@app.route("/")
def home():
    return render_template("submit.html")


# Submit content for moderation
@app.route("/submit", methods=["POST"])
def submit():

    content = request.form.get("content")

    # Basic validation
    if not content or content.strip() == "":
        return "Content cannot be empty"

    # Run AI model
    result = classifier(content)[0]

    model_label = result["label"]
    score = result["score"]

    # Convert model label to our system label
    if model_label.lower() == "toxic" and score >= 0.5:
        label = "toxic"
    else:
        label = "safe"

    # Apply moderation policy
    action, severity = policy_engine(label, score)

    # Save result to database
    conn = sqlite3.connect("database.db")
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


# Moderator action
@app.route("/update/<int:post_id>/<decision>")
def update(post_id, decision):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    conn.commit()
    conn.close()

    return redirect("/dashboard")


# Moderator dashboard
@app.route("/dashboard")
def dashboard():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM posts")
    posts = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM posts")
    total_posts = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        posts=posts,
        total_posts=total_posts
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)