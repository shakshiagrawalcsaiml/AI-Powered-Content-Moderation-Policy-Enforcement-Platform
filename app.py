from flask import Flask, redirect, render_template, request
from transformers import pipeline
import sqlite3

app = Flask(__name__)

# Load AI model once
classifier = pipeline(
    model="unitary/toxic-bert",
    return_all_scores=True
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


@app.route("/")
def home():
    return render_template("submit.html")


@app.route("/submit", methods=["POST"])
def submit():
    content = request.form['content']

    # Run AI model
    result = classifier(content)

    # result[0] is a dict like {'label': 'toxic', 'score': 0.95}
    prediction = result[0]
    
    model_label = prediction.get('label', 'safe')
    score = prediction.get('score', 0)
    
    # Only consider it toxic if score is above threshold
    if model_label == 'toxic' and score >= 0.5:
        label = 'toxic'
    else:
        label = 'safe'

    # policy decision
    action, severity = policy_engine(label, score)

    # save to database
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO posts (content, label, confidence, severity, action)
        VALUES (?, ?, ?, ?, ?)
    """, (content, label, score, severity, action))

    conn.commit()
    conn.close()

    return f"""
    <h3>Moderation Result</h3>

    Content: {content} <br><br>

    Predicted Label: {label} <br>
    Confidence: {score:.2f} <br>
    Severity Score: {severity} <br>
    Final Action: {action} <br><br>

    <a href="/">Submit another content</a><br>
    <a href="/dashboard">Go to Moderator Dashboard</a>
    """
@app.route("/update/<int:post_id>/<decision>")
def update(post_id, decision):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM posts")
    posts = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM posts")
    total_posts = cursor.fetchone()[0]

    conn.close()

    return render_template("dashboard.html", posts=posts, total_posts=total_posts)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)