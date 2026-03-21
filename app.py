from flask import Flask, redirect, render_template, request, session, flash
from transformers import pipeline
import sqlite3
import logging

app = Flask(__name__)
app.secret_key = "super_secret_key"   # change in production

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------- MODEL (LOAD ONCE) ----------------
try:
    classifier = pipeline("text-classification", model="unitary/toxic-bert")
except Exception as e:
    logging.error(f"Model loading failed: {e}")
    classifier = None


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
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row   # better access
    return conn


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


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin":
            session['user'] = username
            logging.info("Admin logged in")
            return redirect("/dashboard")
        else:
            flash("Invalid credentials")
            return redirect("/login")

    return render_template("login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop('user', None)
    logging.info("User logged out")
    return redirect("/login")


# ---------------- SUBMIT ----------------
@app.route("/submit", methods=["POST"])
def submit():

    content = request.form.get("content")

    # ---------------- VALIDATION ----------------
    if not content or content.strip() == "":
        flash("Content cannot be empty")
        return redirect("/")

    if len(content) < 3:
        flash("Content too short")
        return redirect("/")

    if len(content) > 500:
        flash("Content too long")
        return redirect("/")

    if classifier is None:
        return "Model not loaded properly"

    # ---------------- AI PREDICTION ----------------
    try:
        result = classifier(content)[0]
        model_label = result.get("label", "safe")
        score = result.get("score", 0)
    except Exception as e:
        logging.error(f"Prediction error: {e}")
        return "Error processing content"

    # Normalize label
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


# ---------------- UPDATE (PROTECTED) ----------------
@app.route("/update/<int:post_id>/<decision>")
def update(post_id, decision):

    if 'user' not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    logging.info(f"Moderator action on post {post_id}: {decision}")

    cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    conn.commit()
    conn.close()

    return redirect("/dashboard")


# ---------------- DASHBOARD (PROTECTED) ----------------
@app.route("/dashboard")
def dashboard():

    if 'user' not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    posts = cursor.execute("SELECT * FROM posts").fetchall()
    total_posts = cursor.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    toxic_count = cursor.execute("SELECT COUNT(*) FROM posts WHERE label='toxic'").fetchone()[0]
    safe_count = cursor.execute("SELECT COUNT(*) FROM posts WHERE label='safe'").fetchone()[0]

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