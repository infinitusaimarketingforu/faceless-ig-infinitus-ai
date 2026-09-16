import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, init_db


def test_search_filters_ideas():
    with app.test_client() as client:
        init_db()

        client.post("/add", data={"title": "Hook für Reels", "category": "Reels"})
        client.post("/add", data={"title": "Caption für Story", "category": "Story"})

        response = client.get("/?q=Reels")

        assert response.status_code == 200
        assert b"Hook f\xc3\xbcr Reels" in response.data
        assert b"Caption f\xc3\xbcr Story" not in response.data


def test_edit_updates_entry():
    with app.test_client() as client:
        init_db()

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
        init_db()

        client.post("/add", data={"title": "Hook für Reels", "category": "Reels"})
        response = client.get("/?q=NichtVorhanden")

        assert response.status_code == 200
        assert b"Keine Eintr\xc3\xa4ge gefunden" in response.data
