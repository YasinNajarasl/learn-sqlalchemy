"""CRUD-layer tests mirroring the slides."""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from src import crud
from src.models import PostCreate, TagCreate, UserCreate


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


def make_user(session: Session, name: str = "Alice", email: str = "alice@example.com", age: int = 25):
    return crud.create_user(
        session, UserCreate(name=name, email=email, age=age)
    )


def test_create_user_and_post(session: Session):
    alice = make_user(session)
    assert alice.id == 1
    assert alice.created_at is not None

    post = crud.create_post(
        session,
        PostCreate(
            title="Hello ORM",
            content="First post body",
            user_id=alice.id,
        ),
    )
    assert post.id == 1
    assert crud.get_user_with_posts(session, alice.id)["post_count"] == 1

    joined = crud.get_posts_with_users(session, min_age=20)
    assert len(joined) == 1
    assert joined[0][1].name == "Alice"


def test_bulk_insert_and_filters(session: Session):
    for index, (name, age) in enumerate(
        [("Alice", 25), ("Bob", 32), ("Carol", 41), ("David", 19)], start=1
    ):
        crud.create_user(
            session,
            UserCreate(name=name, email=f"{name.lower()}@example.com", age=age),
        )

    assert crud.mass_insert_users(session, count=5) == 5
    assert crud.count_users(session) == 9

    users, total = crud.list_users_filtered(session, q="alice")
    assert total == 1
    assert users[0].name == "Alice"

    users, total = crud.list_users_filtered(
        session, min_age=30, max_age=40, email_domain="example.com"
    )
    assert total == 1
    assert users[0].name == "Bob"

    users, total = crud.list_users_filtered(
        session, sort_by="age", order="desc", limit=3, offset=0
    )
    assert total == 9
    assert [user.age for user in users] == [41, 32, 27]

    page_two, _ = crud.list_users_filtered(
        session, sort_by="age", order="desc", limit=3, offset=3
    )
    assert len(page_two) == 3


def test_tags_many_to_many_and_eager_loading(session: Session):
    alice = make_user(session)
    python_tag = crud.create_tag(session, TagCreate(name="python"))
    orm_tag = crud.create_tag(session, TagCreate(name="orm"))

    post = crud.create_post(
        session,
        PostCreate(
            title="Typed models",
            content="SQLModel is nice.",
            user_id=alice.id,
            tag_ids=[python_tag.id, orm_tag.id],
        ),
    )
    assert {tag.name for tag in post.tags} == {"python", "orm"}

    tags = {tag["name"]: tag for tag in crud.list_tags(session)}
    assert tags["python"]["post_count"] == 1
    assert tags["orm"]["post_count"] == 1

    detached = crud.detach_tag(session, post.id, orm_tag.id)
    assert [tag.name for tag in detached.tags] == ["python"]

    attached = crud.attach_tag(session, post.id, orm_tag.id)
    assert {tag.name for tag in attached.tags} == {"python", "orm"}

    eager_user = crud.get_user_eager(session, alice.id)
    assert eager_user is not None
    assert len(eager_user.posts) == 1
    assert {tag.name for tag in eager_user.posts[0].tags} == {"python", "orm"}


def test_updates_deletes_and_cascade(session: Session):
    alice = make_user(session)
    post = crud.create_post(
        session,
        PostCreate(title="Temp", content="Delete me", user_id=alice.id),
    )

    updated = crud.update_user_age(session, alice.id, 26)
    assert updated.age == 26

    assert crud.mass_increment_user_ages(session) == 1
    assert crud.get_user(session, alice.id).age == 27

    assert crud.delete_post(session, post.id) is True
    assert crud.get_post(session, post.id) is None

    second_post = crud.create_post(
        session,
        PostCreate(title="Cascade", content="Goes with the user", user_id=alice.id),
    )
    assert crud.delete_user(session, alice.id) is True
    assert crud.get_user(session, alice.id) is None
    assert crud.get_post(session, second_post.id) is None


def test_mass_delete_by_author_age(session: Session):
    young = make_user(session, "Young", "young@example.com", 20)
    old = make_user(session, "Old", "old@example.com", 45)
    for user in (young, old):
        crud.create_post(
            session,
            PostCreate(title=f"{user.name} post", content="body", user_id=user.id),
        )

    assert crud.mass_delete_posts_by_author_age(session, age_threshold=30) == 1
    assert crud.count_posts(session) == 1


def test_seed_join_and_group_by(session: Session):
    result = crud.seed_demo_data(session)
    assert result["created"] is True
    assert result["users"] == 8
    assert result["posts"] == 12

    overview = crud.get_overview(session)
    assert overview["users"] == 8
    assert overview["posts"] == 12
    assert overview["tags"] == 6
    assert overview["avg_age"] > 0

    joined = crud.get_posts_with_users(session, min_age=30)
    assert joined
    assert all(user.age > 30 for _post, user in joined)

    per_user = crud.get_posts_per_user(session)
    assert len(per_user) == 8
    assert sum(row["post_count"] for row in per_user) == 12

    ages = crud.get_user_age_stats(session)
    assert sum(row["count"] for row in ages) == 8


def test_transaction_rollback_is_atomic(session: Session):
    alice = make_user(session)
    result = crud.transaction_rollback_demo(session, alice.id, 99)

    assert result["age_before"] == 25
    assert result["age_after"] == 25
    assert result["rolled_back_posts"] == 0
    assert crud.get_user(session, alice.id).age == 25


def test_loading_strategy_demo_reduces_queries(session: Session):
    crud.seed_demo_data(session)
    result = crud.loading_strategy_demo(session)

    assert result["users"] == 8
    assert result["lazy_queries"] > result["eager_queries"]
    assert result["saved_queries"] >= 1
