from flask import Flask, redirect, render_template, request
from transformers import pipeline
import sqlite3
app = Flask(__name__)

# Load AI model once
classifier = pipeline(
    model="unitary/toxic-bert",
    return_all_scores=True
)

def policy_engine(label, score):
    if label.lower() == "toxic" and score > 0.85:
        return "AUTO_REMOVE", 9
    elif label.lower() == "toxic" and score > 0.60:
        return "SEND_TO_MODERATOR", 6
    else:
        return "ALLOW", 2
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

    result = classifier(content)

    # If return_all_scores=True
    if isinstance(result[0], list):
        scores = result[0]
        
        toxic_score = next((x['score'] for x in scores if x['label'] == 'toxic'), 0)
        non_toxic_score = next((x['score'] for x in scores if x['label'] != 'toxic'), 0)

        if toxic_score > non_toxic_score:
            label = "toxic"
            score = toxic_score
        else:
            label = "non-toxic"
            score = non_toxic_score
    else:
        label = result[0]['label']
        score = result[0]['score']

    action, severity = policy_engine(label, score)

    # SAVE TO DATABASE
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
    Final Action: {action}
    """


@app.route("/update/<int:post_id>/<decision>")
def update(post_id, decision):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("UPDATE posts SET action = ? WHERE id = ?", (decision, post_id))

    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM posts")
    posts = cursor.fetchall()

    conn.close()

    return render_template("dashboard.html", posts=posts)

if __name__ == "__main__":
     init_db()
     app.run(debug=True)