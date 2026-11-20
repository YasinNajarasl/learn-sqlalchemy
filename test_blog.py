import pytest
from sqlmodel import SQLModel, create_engine, Session
from models import UserCreate, PostCreate
import crud


@pytest.fixture(name="session")
def session_fixture():
    # Clean in-memory SQLite database for each test (Slide 33)
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_full_blog_workflow(session: Session):
    # Create user & post
    alice = crud.create_user(
        session, UserCreate(name="Alice", email="alice@example.com", age=25)
    )
    assert alice.id == 1

    post = crud.create_post(
        session,
        PostCreate(title="Hello ORM", content="First post body", user_id=alice.id),
    )
    assert post.id == 1

    # Relational join & lazy relationship
    joined = crud.get_posts_with_users(session, min_age=20)
    assert len(joined) == 1
    assert joined[0][1].name == "Alice"

    summary = crud.get_user_with_posts(session, alice.id)
    assert summary["post_count"] == 1

    # Update & Delete
    updated = crud.update_user_age(session, alice.id, 26)
    assert updated.age == 26
    assert crud.delete_post(session, post.id) is True