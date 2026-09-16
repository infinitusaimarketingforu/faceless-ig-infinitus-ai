import json
import os
import sqlite3

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for
from google import genai

app = Flask(__name__)
DB_PATH = "ideas.db"
STATUS_ORDER = ["Neu", "Geplant", "Erstellt", "Veröffentlicht"]
CATEGORY_EMOJIS = {
    "Education": "📚",
    "Entertainment": "🎬",
    "Sales": "💰",
    "Storytelling": "✨",
    "Lifestyle": "🏡",
    "Allgemein": "🗂️",
}

load_dotenv()


def generate_mock_content(topic, category):
    topic = topic.strip() or category
    return {
        "hooks": [
            f"3 Dinge, die du über {topic} wissen solltest",
            f"Der häufigste Fehler bei {topic}",
            f"So wird {topic} ganz einfach erklärt",
        ],
        "script": (
            f"Hook: Starte mit einer überraschenden Aussage über {topic}.\n\n"
            f"Mehrwert: Erkläre in drei kurzen Schritten, was bei {topic} wichtig ist.\n\n"
            "Abschluss: Bitte die Zuschauer, ihre Erfahrung zu kommentieren und dem Account zu folgen."
        ),
        "caption": (
            f"{topic} verständlich erklärt: Speichere dir diese Tipps und teile das Reel "
            "mit jemandem, dem sie helfen können."
        ),
    }


def generate_gemini_content(topic, category, api_key):
    client = genai.Client(api_key=api_key)
    prompt = f"""
Erstelle Instagram-Reel-Inhalte auf Deutsch.
Thema: {topic}

Kategorie: {category}

Antworte ausschließlich als gültiges JSON mit genau diesen Schlüsseln:
{{"hooks": ["Hook 1", "Hook 2", "Hook 3"], "script": "Reel-Skript", "caption": "Caption"}}
Die Liste hooks muss genau drei kurze Vorschläge enthalten.
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = response.text.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    result = json.loads(text)

    if (
        not isinstance(result.get("hooks"), list)
        or len(result["hooks"]) != 3
        or not result.get("script")
        or not result.get("caption")
    ):
        raise ValueError("Gemini-Antwort hat nicht das erwartete Format.")

    return result


def generate_ai_content(topic, category):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return generate_mock_content(topic, category)

    try:
        return generate_gemini_content(topic, category, api_key)
    except Exception:
        return generate_mock_content(topic, category)


def get_saved_hooks(idea):
    try:
        hooks = json.loads(idea["generated_hooks"] or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return hooks if isinstance(hooks, list) else []


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
        for column in ("generated_hooks", "generated_script", "generated_caption"):
            if column not in columns:
                conn.execute(f"ALTER TABLE ideas ADD COLUMN {column} TEXT")


init_db()


@app.route("/", methods=["GET"])
def index():
    conn = get_db_connection()
    search = request.args.get("q", "").strip()
    open_only = request.args.get("open_only") == "1"

    where_clauses = []
    params = []

    if search:
        where_clauses.append("(title LIKE ? OR category LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    if open_only:
        where_clauses.append("status != ?")
        params.append("Veröffentlicht")

    query = "SELECT * FROM ideas"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += """
        ORDER BY CASE status
            WHEN 'Neu' THEN 0
            WHEN 'Geplant' THEN 1
            WHEN 'Erstellt' THEN 2
            WHEN 'Veröffentlicht' THEN 3
            ELSE 4
        END ASC, created_at DESC
    """

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
        open_only=open_only,
        total_count=total_count,
        status_counts=status_counts,
        category_emojis=CATEGORY_EMOJIS,
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

    return render_template(
        "edit.html",
        idea=idea,
        statuses=STATUS_ORDER,
        saved_hooks=get_saved_hooks(idea),
    )


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


@app.route("/generate/<int:id>", methods=["GET", "POST"])
def generate_content(id):
    conn = get_db_connection()
    idea = conn.execute("SELECT * FROM ideas WHERE id = ?", (id,)).fetchone()
    conn.close()

    if idea is None:
        return redirect(url_for("index"))

    topic = idea["title"]
    generated = None
    if request.method == "POST":
        topic = request.form.get("topic", "").strip() or idea["title"]
        generated = generate_ai_content(topic, idea["category"])

    return render_template(
        "generate.html",
        idea=idea,
        topic=topic,
        generated=generated,
    )


@app.route("/save-generated/<int:id>", methods=["POST"])
def save_generated_content(id):
    hooks = request.form.getlist("hooks")
    script = request.form.get("script", "").strip()
    caption = request.form.get("caption", "").strip()

    if len(hooks) != 3 or not script or not caption:
        return redirect(url_for("generate_content", id=id))

    conn = get_db_connection()
    conn.execute(
        """
        UPDATE ideas
        SET generated_hooks = ?, generated_script = ?, generated_caption = ?
        WHERE id = ?
        """,
        (json.dumps(hooks, ensure_ascii=False), script, caption, id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("edit_idea", id=id))


if __name__ == "__main__":
    app.run(debug=True)
