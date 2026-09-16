import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, init_db


def test_search_filters_ideas():
    with app.test_client() as client:
        init_db()

        client.post("/add", data={"title": "Hook für Reels"})
        client.post("/add", data={"title": "Caption für Story"})

        response = client.get("/?q=Reels")

        assert response.status_code == 200
        assert b"Hook f\xc3\xbcr Reels" in response.data
        assert b"Caption f\xc3\xbcr Story" not in response.data
