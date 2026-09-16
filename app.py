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
                category TEXT NOT NULL DEFAULT 'Allgemein',
                status TEXT NOT NULL DEFAULT 'Neu',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        columns = [row[1] for row in conn.execute("PRAGMA table_info(ideas)").fetchall()]
        if "category" not in columns:
            conn.execute(
                "ALTER TABLE ideas ADD COLUMN category TEXT NOT NULL DEFAULT 'Allgemein'"
            )


init_db()


@app.route("/", methods=["GET"])
def index():
    conn = get_db_connection()
    search = request.args.get("q", "").strip()

    if search:
        query = """
            SELECT * FROM ideas
            WHERE title LIKE ? OR category LIKE ?
            ORDER BY CASE status
                WHEN 'Neu' THEN 0
                WHEN 'Geplant' THEN 1
                WHEN 'Erstellt' THEN 2
                WHEN 'Veröffentlicht' THEN 3
                ELSE 4
            END ASC, created_at DESC
        """
        params = (f"%{search}%", f"%{search}%")
    else:
        query = """
            SELECT * FROM ideas
            ORDER BY CASE status
                WHEN 'Neu' THEN 0
                WHEN 'Geplant' THEN 1
                WHEN 'Erstellt' THEN 2
                WHEN 'Veröffentlicht' THEN 3
                ELSE 4
            END ASC, created_at DESC
        """
        params = ()

    ideas = conn.execute(query, params).fetchall()
    status_counts = {status: 0 for status in STATUS_ORDER}
    for idea in ideas:
        status_counts[idea["status"]] = status_counts.get(idea["status"], 0) + 1
    total_count = len(ideas)
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
    category = request.form.get("category", "Allgemein").strip() or "Allgemein"
    if title:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO ideas (title, category, status) VALUES (?, ?, 'Neu')",
            (title, category),
        )
        conn.commit()
        conn.close()
    return redirect(url_for("index"))


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_idea(id):
    conn = get_db_connection()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "Allgemein").strip() or "Allgemein"
        status = request.form.get("status", "Neu")

        if title:
            conn.execute(
                "UPDATE ideas SET title = ?, category = ?, status = ? WHERE id = ?",
                (title, category, status, id),
            )
            conn.commit()
        conn.close()
        return redirect(url_for("index"))

    idea = conn.execute("SELECT * FROM ideas WHERE id = ?", (id,)).fetchone()
    conn.close()

    if idea is None:
        return redirect(url_for("index"))

    return render_template("edit.html", idea=idea, statuses=STATUS_ORDER)


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
