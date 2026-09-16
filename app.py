from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)
DB_PATH = "ideas.db"
STATUS_ORDER = ["Neu", "Geplant", "Erstellt", "Veröffentlicht"]


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Neu',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


init_db()


@app.route("/", methods=["GET"])
def index():
    conn = get_db_connection()
    search = request.args.get("q", "").strip()

    if search:
        query = "SELECT * FROM ideas WHERE title LIKE ? ORDER BY created_at DESC"
        params = (f"%{search}%",)
    else:
        query = "SELECT * FROM ideas ORDER BY created_at DESC"
        params = ()

    ideas = conn.execute(query, params).fetchall()
    status_counts = {
        status: conn.execute(
            "SELECT COUNT(*) FROM ideas WHERE status = ?",
            (status,),
        ).fetchone()[0]
        for status in STATUS_ORDER
    }
    total_count = sum(status_counts.values())
    conn.close()

    return render_template(
        "index.html",
        ideas=ideas,
        search=search,
        total_count=total_count,
        status_counts=status_counts,
    )


@app.route("/add", methods=["POST"])
def add_idea():
    title = request.form.get("title", "").strip()
    if title:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO ideas (title, status) VALUES (?, 'Neu')",
            (title,),
        )
        conn.commit()
        conn.close()
    return redirect(url_for("index"))


@app.route("/update_status/<int:id>", methods=["POST"])
def update_status(id):
    status = request.form.get("status", "Neu")
    conn = get_db_connection()
    conn.execute(
        "UPDATE ideas SET status = ? WHERE id = ?",
        (status, id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/delete/<int:id>", methods=["POST"])
def delete_idea(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM ideas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
