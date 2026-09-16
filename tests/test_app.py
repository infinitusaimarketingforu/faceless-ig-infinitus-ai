import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, init_db


def reset_db():
    import sqlite3

    conn = sqlite3.connect(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ideas.db")))
    conn.execute("DELETE FROM ideas")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='ideas'")
    conn.commit()
    conn.close()
    init_db()


def test_search_filters_ideas():
    with app.test_client() as client:
        reset_db()

        client.post("/add", data={"title": "Hook für Reels", "category": "Reels"})
        client.post("/add", data={"title": "Caption für Story", "category": "Story"})

        response = client.get("/?q=Reels")

        assert response.status_code == 200
        assert b"Hook f\xc3\xbcr Reels" in response.data
        assert b"Caption f\xc3\xbcr Story" not in response.data


def test_edit_updates_entry():
    with app.test_client() as client:
        reset_db()

        client.post("/add", data={"title": "Alte Idee", "category": "Reels"})

        response = client.post(
            "/edit/1",
            data={
                "title": "Neue Idee",
                "category": "Story",
                "status": "Geplant",
            },
        )

        assert response.status_code == 302
        page = client.get("/")
        assert b"Neue Idee" in page.data
        assert b"Story" in page.data
        assert b"Geplant" in page.data


def test_empty_search_message():
    with app.test_client() as client:
        reset_db()

        client.post("/add", data={"title": "Hook für Reels", "category": "Reels"})
        response = client.get("/?q=NichtVorhanden")

        assert response.status_code == 200
        assert b"Keine Eintr\xc3\xa4ge gefunden" in response.data


def test_open_only_filter_works():
    with app.test_client() as client:
        reset_db()

        client.post("/add", data={"title": "Offene Idee", "category": "Education"})
        client.post("/add", data={"title": "Veröffentlichte Idee", "category": "Sales"})
        client.post("/update_status/2", data={"status": "Veröffentlicht"})

        response = client.get("/?open_only=1")

        assert response.status_code == 200
        assert b"Offene Idee" in response.data
        assert b"Ver\xc3\xb6ffentlichte Idee" not in response.data


def test_category_emoji_is_shown():
    with app.test_client() as client:
        reset_db()

        client.post("/add", data={"title": "Test Idee", "category": "Education"})
        page = client.get("/")

        assert page.status_code == 200
        assert b"\xf0\x9f\x93\x9a" in page.data


def test_mock_ai_generates_hooks_script_and_caption(monkeypatch):
    with app.test_client() as client:
        reset_db()
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        client.post("/add", data={"title": "Content-Planung", "category": "Education"})
        response = client.post(
            "/generate/1",
            data={"topic": "Content-Planung für Anfänger"},
        )

        assert response.status_code == 200
        assert "3 Dinge, die du über Content-Planung für Anfänger wissen solltest".encode() in response.data
        assert "Der häufigste Fehler bei Content-Planung für Anfänger".encode() in response.data
        assert "So wird Content-Planung für Anfänger ganz einfach erklärt".encode() in response.data
        assert b"Reel-Skript" in response.data
        assert b"Caption" in response.data


def test_generated_content_can_be_saved_and_shown_in_edit_view(monkeypatch):
    with app.test_client() as client:
        reset_db()
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        client.post("/add", data={"title": "Sommer-Reels", "category": "Lifestyle"})
        generated = client.post(
            "/generate/1",
            data={"topic": "Sommer-Reels"},
        )
        assert generated.status_code == 200

        saved = client.post(
            "/save-generated/1",
            data={
                "hooks": ["Hook A", "Hook B", "Hook C"],
                "script": "Ein gespeichertes Reel-Skript.",
                "caption": "Eine gespeicherte Caption.",
                "image_prompt": "Ein gespeicherter Bildprompt.",
                "video_prompt": "Ein gespeicherter Videoprompt.",
                "selected_variant": "B",
                "variations": "[]",
            },
        )

        assert saved.status_code == 302
        edit_page = client.get("/edit/1")
        assert b"Gespeicherte KI-Texte" in edit_page.data
        assert b"Hook A" in edit_page.data
        assert b"Hook B" in edit_page.data
        assert b"Hook C" in edit_page.data
        assert b"Ein gespeichertes Reel-Skript." in edit_page.data
        assert b"Eine gespeicherte Caption." in edit_page.data
        assert b"Ein gespeicherter Bildprompt." in edit_page.data
        assert b"Ein gespeicherter Videoprompt." in edit_page.data


def test_mock_ai_returns_three_variations_and_prompts(monkeypatch):
    with app.test_client() as client:
        reset_db()
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        client.post("/add", data={"title": "Produktivität", "category": "Education"})
        response = client.post("/generate/1", data={"topic": "Produktivität"})

        assert response.status_code == 200
        assert response.data.count(b"Variante ") >= 3
        assert b"Bild-Prompt" in response.data
        assert b"Video-Prompt" in response.data
        assert b"Variante B speichern" in response.data


def test_calendar_sorts_ideas_by_scheduled_time():
    with app.test_client() as client:
        reset_db()

        client.post(
            "/add",
            data={"title": "Später geplant", "category": "Sales", "scheduled_at": "2026-10-20T18:00"},
        )
        client.post(
            "/add",
            data={"title": "Früher geplant", "category": "Education", "scheduled_at": "2026-10-05T09:00"},
        )

        calendar_page = client.get("/calendar")

        assert calendar_page.status_code == 200
        assert calendar_page.data.index("Früher geplant".encode()) < calendar_page.data.index("Später geplant".encode())
        dashboard_page = client.get("/")
        assert dashboard_page.data.index("Früher geplant".encode()) < dashboard_page.data.index("Später geplant".encode())
