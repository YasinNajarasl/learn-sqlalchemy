from typing import List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import User, UserCreate, Post, PostCreate
from database import engine


# STEP 3 – Single Data Insertion
def create_user(session: Session, user_in: UserCreate) -> User:
    user = User.model_validate(user_in)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# STEP 4 – Mass Data Insertion
def mass_insert_users(session: Session, count: int = 100) -> int:
    users_data = [
        {"name": f"User {i}", "email": f"user{i}@example.com", "age": i + 18}
        for i in range(1, count + 1)
    ]
    session.bulk_insert_mappings(User, users_data)
    session.commit()
    return count


# STEP 5 – Relational Data Insertion
def create_post(session: Session, post_in: PostCreate) -> Post:
    post = Post.model_validate(post_in)
    session.add(post)
    session.commit()
    session.refresh(post)
    return post


# STEP 6 – Select Data (with conditions & pagination)
def get_user_by_name(session: Session, name: str) -> Optional[User]:
    statement = select(User).where(User.name == name)
    return session.exec(statement).first()


def list_users(session: Session, limit: int = 10, offset: int = 0) -> List[User]:
    statement = select(User).offset(offset).limit(limit)
    return list(session.exec(statement).all())


# STEP 7 – Advanced Relational Select (Join)
def get_posts_with_users(session: Session, min_age: int = 20) -> List[Tuple[Post, User]]:
    statement = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(User.age > min_age)
    )
    return list(session.exec(statement).all())


# STEP 8 – Update Single Record
def update_user_age(session: Session, user_id: int, new_age: int) -> Optional[User]:
    user = session.get(User, user_id)
    if not user:
        return None
    user.age = new_age
    session.commit()
    session.refresh(user)
    return user


# STEP 9 – Mass Update Record
def mass_increment_user_ages(session: Session) -> int:
    users = session.exec(select(User)).all()
    for user in users:
        user.age += 1
    session.commit()
    return len(users)


# STEP 10 – Delete Single Record
def delete_post(session: Session, post_id: int) -> bool:
    post = session.get(Post, post_id)
    if not post:
        return False
    session.delete(post)
    session.commit()
    return True


# STEP 11 – Mass Deletion
def mass_delete_posts_by_author_age(session: Session, age_threshold: int = 30) -> int:
    statement = select(Post).join(User).where(User.age > age_threshold)
    posts = session.exec(statement).all()
    count = len(posts)
    for post in posts:
        session.delete(post)
    session.commit()
    return count


# STEP 12A – Relationships & Lazy Loading
def get_user_with_posts(session: Session, user_id: int) -> Optional[dict]:
    user = session.get(User, user_id)
    if not user:
        return None
    return {
        "user": user.name,
        "post_count": len(user.posts),
        "posts": [p.title for p in user.posts],
    }


# STEP 12B – Atomic Transaction (All-or-Nothing)
def update_age_and_publish_post(
    session: Session, user_id: int, new_age: int, title: str, content: str
) -> Post:
    user = session.get(User, user_id)
    if not user:
        raise ValueError("User not found")
    user.age = new_age
    post = Post(title=title, content=content, user_id=user_id)
    session.add(post)
    session.commit()
    session.refresh(post)
    return post


# STEP 12C – Database Stats via Parameterized SQL text()
def get_user_age_stats(session: Session) -> List[dict]:
    stmt = text("SELECT age, COUNT(*) AS count FROM user GROUP BY age ORDER BY age")
    rows = session.exec(stmt).all()
    return [{"age": row[0], "count": row[1]} for row in rows]


# STEP 12D – Async Query with Eager Loading (selectinload)
async def async_get_user_with_posts(
    async_session: AsyncSession, user_id: int
) -> Optional[User]:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.posts))
    )
    result = await async_session.exec(stmt)
    return result.first()


if __name__ == "__main__":
    from database import init_db

    init_db()
    with Session(engine) as demo_session:
        alice = create_user(
            demo_session,
            UserCreate(name="Alice", email="alice@example.com", age=25),
        )
        print(f"Created User: {alice.name} (ID: {alice.id})")
        post = create_post(
            demo_session,
            PostCreate(title="My first post", content="Hello world!", user_id=alice.id),
        )
        print(f"Created Post: {post.title} (ID: {post.id})")