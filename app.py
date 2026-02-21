from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("submit.html")

@app.route("/submit", methods=["POST"])
def submit():
    content = request.form['content']
    return f"You submitted: {content}"

if __name__ == "__main__":
    app.run(debug=True)