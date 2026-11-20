"""HTTP API tests for the FastAPI layer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as client:
        client.post("/demo/reset?seed=true")
        yield client


def test_health_and_ui(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    page = client.get("/")
    assert page.status_code == 200
    assert "SQLAlchemy Lab" in page.text
    slides = client.get("/static/slide_map.json").json()
    assert [slide["slide"] for slide in slides] == list(range(1, 46))
    assert "session.add(user)" in slides[16]["text"]
    assert slides[16]["symbol"] == "create_user"


def test_learn_workbook_has_runnable_starters(client: TestClient):
    course = client.get("/learn/workbook").json()
    assert len(course["lessons"]) == 12
    assert [category["name"] for category in course["categories"]][0] == "Foundations"
    first = course["lessons"][0]
    assert first["starter"].startswith("with engine.connect()")
    assert "TODO" in first["starter"]
    assert first["code"] != first["starter"]


def test_persian_lessons_share_executable_examples(client: TestClient):
    english = client.get("/learn/workbook").json()
    persian = client.get("/learn/workbook?lang=fa").json()
    for en, fa in zip(english["lessons"], persian["lessons"], strict=True):
        for key in ("title", "explanation", "hint", "exercise", "goal"):
            assert any("\u0600" <= char <= "\u06ff" for char in fa[key])
        for key in ("number", "code", "starter", "output"):
            assert en[key] == fa[key]
    assert client.get("/openapi.json").json()["info"]["contact"]["name"] == "Yasin"


def test_lab_runs_against_practice_copy(client: TestClient):
    code = """
with Session(engine) as s:
    print([u.name for u in s.scalars(select(User).where(User.email == 'alice@example.com'))])
"""
    response = client.post("/lab/run", json={"code": code})
    assert response.status_code == 200
    result = response.json()
    assert result["error"] is None
    assert "Alice Johnson" in result["stdout"]
    assert result["mode"] == "practice"
    assert any(query["sql"].startswith("SELECT") for query in result["sql"])

    write = """
with Session(engine) as s, s.begin():
    s.add(User(name="Practice Only", email="practice.only@example.com", age=30))
"""
    assert client.post("/lab/run", json={"code": write}).json()["error"] is None
    assert client.get("/users/by-name/Practice Only").status_code == 404


def test_lab_can_write_to_live_database(client: TestClient):
    code = """
with Session(engine) as s, s.begin():
    s.add(User(name="Lab User", email="lab.user@example.com", age=30))
"""
    response = client.post("/lab/run", json={"code": code, "live": True})
    assert response.status_code == 200
    assert response.json()["error"] is None
    assert response.json()["mode"] == "live"
    assert client.get("/users/by-name/Lab User").status_code == 200


def test_lab_blocks_imports_and_reports_schema(client: TestClient):
    blocked = client.post("/lab/run", json={"code": "import os"}).json()
    assert "not available in the lab" in blocked["error"]

    schema = client.get("/lab/schema").json()
    tables = {table["name"]: table for table in schema["tables"]}
    assert set(tables) == {"users", "posts", "tags", "post_tags"}
    assert tables["users"]["rows"] >= 8
    assert any(column["primary_key"] for column in tables["users"]["columns"])


def test_users_crud_and_filtering(client: TestClient):
    created = client.post(
        "/users/",
        json={
            "name": "Test User",
            "email": "test.user@example.com",
            "age": 29,
            "bio": "Created from pytest",
        },
    )
    assert created.status_code == 200
    user_id = created.json()["id"]

    listing = client.get("/users/?q=test.user&min_age=20&sort_by=name&order=asc")
    assert listing.status_code == 200
    assert listing.headers["x-total-count"] == "1"
    assert listing.json()[0]["name"] == "Test User"

    updated = client.patch(f"/users/{user_id}/age?new_age=31")
    assert updated.status_code == 200
    assert updated.json()["age"] == 31

    detail = client.get(f"/users/{user_id}")
    assert detail.status_code == 200
    assert detail.json()["email"] == "test.user@example.com"

    deleted = client.delete(f"/users/{user_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_posts_tags_and_join(client: TestClient):
    users = client.get("/users/?limit=1").json()
    tags = client.get("/tags/").json()
    assert users and tags

    created = client.post(
        "/posts/",
        json={
            "title": "API-created post",
            "content": "The body is long enough.",
            "user_id": users[0]["id"],
            "tag_ids": [tags[0]["id"]],
        },
    )
    assert created.status_code == 200
    post = created.json()
    assert post["tags"][0]["name"] == tags[0]["name"]

    detail = client.get(f"/posts/{post['id']}")
    assert detail.status_code == 200
    assert detail.json()["author"]["id"] == users[0]["id"]

    listing = client.get(f"/posts/?user_id={users[0]['id']}&tag_id={tags[0]['id']}")
    assert listing.status_code == 200
    assert int(listing.headers["x-total-count"]) >= 1

    joined = client.get("/posts/with-users/?min_age=20")
    assert joined.status_code == 200
    assert isinstance(joined.json(), list)

    detached = client.delete(f"/posts/{post['id']}/tags/{tags[0]['id']}")
    assert detached.status_code == 200
    assert detached.json()["tags"] == []

    attached = client.post(f"/posts/{post['id']}/tags/{tags[0]['id']}")
    assert attached.status_code == 200
    assert attached.json()["tags"][0]["id"] == tags[0]["id"]

    deleted = client.delete(f"/posts/{post['id']}")
    assert deleted.status_code == 200


def test_async_and_relationship_endpoints(client: TestClient):
    async_response = client.get("/users/1/async")
    assert async_response.status_code == 200
    assert async_response.json()["posts"]

    eager = client.get("/users/1/eager")
    assert eager.status_code == 200
    assert eager.json()["posts"]

    loading = client.get("/relationships/loading-demo")
    assert loading.status_code == 200
    payload = loading.json()
    assert payload["lazy_queries"] > payload["eager_queries"]


def test_transactions_and_statistics(client: TestClient):
    atomic = client.post(
        "/transactions/update-age-and-publish",
        json={
            "user_id": 1,
            "new_age": 33,
            "title": "Committed post",
            "content": "Both changes should commit.",
        },
    )
    assert atomic.status_code == 200
    assert atomic.json()["committed"] is True

    rollback = client.post(
        "/transactions/rollback-demo",
        json={"user_id": 1, "new_age": 99},
    )
    assert rollback.status_code == 200
    assert rollback.json()["age_after"] == 33
    assert rollback.json()["rolled_back_posts"] == 0

    for path in ("/stats/overview", "/stats/user-ages", "/stats/posts-per-user"):
        response = client.get(path)
        assert response.status_code == 200


def test_debug_endpoints(client: TestClient):
    client.get("/users/?limit=2")
    log = client.get("/debug/sql-log")
    assert log.status_code == 200
    assert isinstance(log.json(), list)

    pool = client.get("/debug/pool")
    assert pool.status_code == 200
    assert "pool" in pool.json()

    events = client.get("/debug/events")
    assert events.status_code == 200
    assert isinstance(events.json(), list)

    cleared = client.delete("/debug/sql-log")
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] is True


def test_duplicate_email_returns_409(client: TestClient):
    response = client.post(
        "/users/",
        json={
            "name": "Duplicate",
            "email": "alice@example.com",
            "age": 20,
        },
    )
    assert response.status_code == 409
