"""CRUD and query helpers — the heart of the tutorial.

Every function is intentionally small and named after the slide that
introduces it.  The FastAPI routes in :mod:`src.main` are thin wrappers
around these functions.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import delete, func, or_, text
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .database import get_query_count, reset_query_counter
from .models import (
    Post,
    PostCreate,
    PostTag,
    Tag,
    TagCreate,
    User,
    UserCreate,
    utcnow,
)


# ---------------------------------------------------------------------------
# Counts used by the dashboard
# ---------------------------------------------------------------------------
def count_users(session: Session) -> int:
    return int(session.exec(select(func.count()).select_from(User)).one())


def count_posts(session: Session) -> int:
    return int(session.exec(select(func.count()).select_from(Post)).one())


def count_tags(session: Session) -> int:
    return int(session.exec(select(func.count()).select_from(Tag)).one())


# ---------------------------------------------------------------------------
# Slide 17 — single insert
# ---------------------------------------------------------------------------
def create_user(session: Session, user_in: UserCreate) -> User:
    user = User.model_validate(user_in)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Slide 18 — bulk insert
# ---------------------------------------------------------------------------
def mass_insert_users(session: Session, count: int = 100) -> int:
    batch = uuid4().hex
    existing = count_users(session)
    now = utcnow()
    users_data = [
        {
            "name": f"User {existing + i}",
            "email": f"user{i}.{batch}@example.com",
            "age": 18 + ((existing + i) % 50),
            "bio": "Created by the bulk-insert demo",
            "created_at": now,
        }
        for i in range(1, count + 1)
    ]
    session.bulk_insert_mappings(User, users_data)
    session.commit()
    return count


# ---------------------------------------------------------------------------
# Slide 26 — insert a related row
# ---------------------------------------------------------------------------
def create_post(session: Session, post_in: PostCreate) -> Post:
    data = post_in.model_dump(exclude={"tag_ids"})
    post = Post.model_validate(data)
    if post_in.tag_ids:
        tags = list(
            session.exec(select(Tag).where(Tag.id.in_(post_in.tag_ids))).all()
        )
        post.tags = tags
    session.add(post)
    session.commit()
    session.refresh(post)
    return post


# ---------------------------------------------------------------------------
# Slide 19 — select one row / basic list
# ---------------------------------------------------------------------------
def get_user_by_name(session: Session, name: str) -> Optional[User]:
    statement = select(User).where(User.name == name)
    return session.exec(statement).first()


def get_user(session: Session, user_id: int) -> Optional[User]:
    return session.get(User, user_id)


def list_users(session: Session, limit: int = 10, offset: int = 0) -> List[User]:
    statement = select(User).offset(offset).limit(limit)
    return list(session.exec(statement).all())


# ---------------------------------------------------------------------------
# Slides 20/21 — filtering, sorting and pagination
# ---------------------------------------------------------------------------
def list_users_filtered(
    session: Session,
    *,
    q: Optional[str] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    email_domain: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc",
    limit: int = 10,
    offset: int = 0,
) -> Tuple[List[User], int]:
    conditions = []
    if q:
        pattern = f"%{q}%"
        conditions.append(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    if min_age is not None:
        conditions.append(User.age >= min_age)
    if max_age is not None:
        conditions.append(User.age <= max_age)
    if email_domain:
        domain = email_domain.lstrip("@")
        conditions.append(User.email.endswith(f"@{domain}"))

    sort_columns = {
        "id": User.id,
        "name": User.name,
        "email": User.email,
        "age": User.age,
        "created_at": User.created_at,
    }
    sort_column = sort_columns.get(sort_by, User.id)
    if order.lower() == "desc":
        sort_column = sort_column.desc()

    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    stmt = stmt.order_by(sort_column).offset(offset).limit(limit)
    users = list(session.exec(stmt).all())
    total = int(session.exec(count_stmt).one())
    return users, total


# ---------------------------------------------------------------------------
# Slide 30 — join Post and User
# ---------------------------------------------------------------------------
def get_posts_with_users(
    session: Session, min_age: int = 20
) -> List[Tuple[Post, User]]:
    statement = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(User.age > min_age)
        .order_by(Post.id)
    )
    return list(session.exec(statement).all())


# ---------------------------------------------------------------------------
# Slide 22 — update one row / mass update
# ---------------------------------------------------------------------------
def update_user_age(
    session: Session, user_id: int, new_age: int
) -> Optional[User]:
    user = session.get(User, user_id)
    if not user:
        return None
    user.age = new_age
    session.commit()
    session.refresh(user)
    return user


def mass_increment_user_ages(session: Session) -> int:
    users = list(session.exec(select(User)).all())
    for user in users:
        user.age += 1
    session.commit()
    return len(users)


# ---------------------------------------------------------------------------
# Slide 23 — delete one row / mass delete
# ---------------------------------------------------------------------------
def delete_post(session: Session, post_id: int) -> bool:
    post = session.get(Post, post_id)
    if not post:
        return False
    session.execute(delete(PostTag).where(PostTag.post_id == post_id))
    session.delete(post)
    session.commit()
    return True


def delete_user(session: Session, user_id: int) -> bool:
    user = session.get(User, user_id)
    if not user:
        return False
    post_ids = list(
        session.exec(select(Post.id).where(Post.user_id == user_id)).all()
    )
    if post_ids:
        session.execute(delete(PostTag).where(PostTag.post_id.in_(post_ids)))
    session.delete(user)
    session.commit()
    return True


def mass_delete_posts_by_author_age(
    session: Session, age_threshold: int = 30
) -> int:
    statement = select(Post).join(User).where(User.age > age_threshold)
    posts = list(session.exec(statement).all())
    post_ids = [post.id for post in posts if post.id is not None]
    if post_ids:
        session.execute(delete(PostTag).where(PostTag.post_id.in_(post_ids)))
        session.execute(delete(Post).where(Post.id.in_(post_ids)))
    session.commit()
    return len(posts)


# ---------------------------------------------------------------------------
# Slide 26/29 — relationships and eager loading
# ---------------------------------------------------------------------------
def get_user_with_posts(session: Session, user_id: int) -> Optional[dict]:
    user = session.get(User, user_id)
    if not user:
        return None
    return {
        "user": user.name,
        "post_count": len(user.posts),
        "posts": [post.title for post in user.posts],
    }


def get_user_eager(session: Session, user_id: int) -> Optional[User]:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.posts).selectinload(Post.tags))
    )
    return session.exec(stmt).first()


def get_posts_eager(session: Session, limit: int = 20) -> List[Post]:
    stmt = (
        select(Post)
        .options(selectinload(Post.author), selectinload(Post.tags))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def list_posts_filtered(
    session: Session,
    *,
    q: Optional[str] = None,
    user_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = 10,
    offset: int = 0,
) -> Tuple[List[Post], int]:
    conditions = []
    if q:
        pattern = f"%{q}%"
        conditions.append(or_(Post.title.ilike(pattern), Post.content.ilike(pattern)))
    if user_id is not None:
        conditions.append(Post.user_id == user_id)

    stmt = select(Post).options(
        selectinload(Post.author), selectinload(Post.tags)
    )
    count_stmt = select(func.count(func.distinct(Post.id))).select_from(Post)

    if tag_id is not None:
        stmt = stmt.join(PostTag, PostTag.post_id == Post.id)
        count_stmt = count_stmt.join(PostTag, PostTag.post_id == Post.id)
        conditions.append(PostTag.tag_id == tag_id)

    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    sort_columns = {
        "id": Post.id,
        "title": Post.title,
        "created_at": Post.created_at,
        "user_id": Post.user_id,
    }
    sort_column = sort_columns.get(sort_by, Post.created_at)
    if order.lower() == "asc":
        sort_column = sort_column.asc()
    else:
        sort_column = sort_column.desc()

    stmt = stmt.order_by(sort_column, Post.id.desc()).offset(offset).limit(limit)
    posts = list(session.exec(stmt).all())
    total = int(session.exec(count_stmt).one())
    return posts, total


def get_post(session: Session, post_id: int) -> Optional[Post]:
    stmt = (
        select(Post)
        .where(Post.id == post_id)
        .options(selectinload(Post.author), selectinload(Post.tags))
    )
    return session.exec(stmt).first()


# ---------------------------------------------------------------------------
# Slide 27 — tags (many-to-many)
# ---------------------------------------------------------------------------
def create_tag(session: Session, tag_in: TagCreate) -> Tag:
    tag = Tag(name=tag_in.name.strip())
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def list_tags(session: Session) -> List[dict]:
    stmt = (
        select(Tag, func.count(PostTag.post_id).label("post_count"))
        .outerjoin(PostTag, PostTag.tag_id == Tag.id)
        .group_by(Tag.id, Tag.name)
        .order_by(Tag.name)
    )
    rows = session.exec(stmt).all()
    return [
        {"id": tag.id, "name": tag.name, "post_count": int(post_count)}
        for tag, post_count in rows
    ]


def delete_tag(session: Session, tag_id: int) -> bool:
    tag = session.get(Tag, tag_id)
    if not tag:
        return False
    session.execute(delete(PostTag).where(PostTag.tag_id == tag_id))
    session.delete(tag)
    session.commit()
    return True


def attach_tag(session: Session, post_id: int, tag_id: int) -> Optional[Post]:
    post = get_post(session, post_id)
    tag = session.get(Tag, tag_id)
    if not post or not tag:
        return None
    if tag not in post.tags:
        post.tags.append(tag)
        session.commit()
    return get_post(session, post_id)


def detach_tag(session: Session, post_id: int, tag_id: int) -> Optional[Post]:
    post = get_post(session, post_id)
    tag = session.get(Tag, tag_id)
    if not post or not tag:
        return None
    if tag in post.tags:
        post.tags.remove(tag)
        session.commit()
    return get_post(session, post_id)


# ---------------------------------------------------------------------------
# Slide 31 — GROUP BY and aggregates
# ---------------------------------------------------------------------------
def get_posts_per_user(session: Session) -> List[dict]:
    stmt = (
        select(User.id, User.name, func.count(Post.id).label("post_count"))
        .join(Post, Post.user_id == User.id, isouter=True)
        .group_by(User.id, User.name)
        .order_by(func.count(Post.id).desc(), User.name)
    )
    rows = session.exec(stmt).all()
    return [
        {"user_id": row[0], "name": row[1], "post_count": int(row[2])}
        for row in rows
    ]


def get_user_age_stats(session: Session) -> List[dict]:
    """Raw SQL counterpart to the slide 31 aggregate."""
    stmt = text(
        "SELECT age, COUNT(*) AS count FROM users GROUP BY age ORDER BY age"
    )
    rows = session.execute(stmt).all()
    return [{"age": int(row[0]), "count": int(row[1])} for row in rows]


# ---------------------------------------------------------------------------
# Slide 32 — transactions
# ---------------------------------------------------------------------------
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


def transaction_rollback_demo(
    session: Session, user_id: int, new_age: int
) -> dict:
    """Flush two changes, then roll them back to prove all-or-nothing."""
    user = session.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    original_age = user.age
    user.age = new_age
    post = Post(
        title="Rolled back post",
        content="This row must never be visible after the rollback.",
        user_id=user_id,
    )
    session.add(post)
    session.flush()

    session.rollback()

    fresh = session.get(User, user_id)
    rolled_back_posts = int(
        session.exec(
            select(func.count())
            .select_from(Post)
            .where(Post.title == "Rolled back post")
        ).one()
    )
    return {
        "user_id": user_id,
        "age_before": original_age,
        "attempted_age": new_age,
        "age_after": fresh.age if fresh else None,
        "rolled_back_posts": rolled_back_posts,
        "rolled_back": True,
    }


# ---------------------------------------------------------------------------
# Slide 29 — lazy vs eager loading, measured with a SQL counter
# ---------------------------------------------------------------------------
def loading_strategy_demo(session: Session) -> dict:
    reset_query_counter()
    users = list(session.exec(select(User)).all())
    for user in users:
        _ = [post.title for post in user.posts]
    lazy_queries = get_query_count()

    session.expire_all()
    reset_query_counter()
    stmt = select(User).options(selectinload(User.posts))
    users = list(session.exec(stmt).all())
    for user in users:
        _ = [post.title for post in user.posts]
    eager_queries = get_query_count()

    return {
        "users": len(users),
        "lazy_queries": lazy_queries,
        "eager_queries": eager_queries,
        "saved_queries": max(lazy_queries - eager_queries, 0),
        "explanation": (
            "Lazy loading runs one extra SELECT per user (the N+1 problem). "
            "selectinload() fetches all posts in a single extra SELECT."
        ),
    }


# ---------------------------------------------------------------------------
# Slide 35 — async query with eager loading
# ---------------------------------------------------------------------------
async def async_get_user_with_posts(
    async_session: AsyncSession, user_id: int
) -> Optional[User]:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.posts).selectinload(Post.tags))
    )
    result = await async_session.exec(stmt)
    return result.first()


# ---------------------------------------------------------------------------
# Dashboard aggregate
# ---------------------------------------------------------------------------
def get_overview(session: Session) -> dict:
    avg_age = session.exec(select(func.avg(User.age))).one()
    recent = list(
        session.exec(
            select(Post)
            .options(selectinload(Post.author))
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(5)
        ).all()
    )
    return {
        "users": count_users(session),
        "posts": count_posts(session),
        "tags": count_tags(session),
        "avg_age": round(float(avg_age), 1) if avg_age is not None else 0,
        "recent_posts": [
            {
                "id": post.id,
                "title": post.title,
                "author": post.author.name if post.author else "Unknown",
                "created_at": post.created_at,
            }
            for post in recent
        ],
        "posts_per_user": get_posts_per_user(session),
        "age_distribution": get_user_age_stats(session),
    }


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------
def seed_demo_data(session: Session) -> dict:
    existing = count_users(session)
    if existing:
        return {
            "created": False,
            "message": "Database already contains users; seed skipped.",
            "users": existing,
            "posts": count_posts(session),
            "tags": count_tags(session),
        }

    users = [
        User(
            name="Alice Johnson",
            email="alice@example.com",
            age=25,
            bio="Backend engineer who loves clean data models.",
        ),
        User(
            name="Bob Smith",
            email="bob@example.com",
            age=32,
            bio="FastAPI and async enthusiast.",
        ),
        User(
            name="Carol Danvers",
            email="carol@example.com",
            age=41,
            bio="Database reliability engineer.",
        ),
        User(
            name="David Kim",
            email="david@example.com",
            age=19,
            bio="Student learning ORMs from scratch.",
        ),
        User(
            name="Emma Wilson",
            email="emma@example.com",
            age=28,
            bio="Writes tests before features.",
        ),
        User(
            name="Farid Ahmadi",
            email="farid@example.com",
            age=35,
            bio="Loves many-to-many relationships.",
        ),
        User(
            name="Grace Lee",
            email="grace@example.com",
            age=22,
            bio="Interested in transactions and consistency.",
        ),
        User(
            name="Hassan Rezaei",
            email="hassan@example.com",
            age=47,
            bio="Query optimisation veteran.",
        ),
    ]
    session.add_all(users)
    session.flush()

    tags = [
        Tag(name="python"),
        Tag(name="sqlalchemy"),
        Tag(name="fastapi"),
        Tag(name="database"),
        Tag(name="orm"),
        Tag(name="tutorial"),
    ]
    session.add_all(tags)
    session.flush()

    tag_by_name = {tag.name: tag for tag in tags}
    user_by_name = {user.name: user for user in users}

    post_specs = [
        ("Getting started with SQLAlchemy", "A gentle tour of Engine, Session and models.", "Alice Johnson", ["python", "sqlalchemy", "tutorial"]),
        ("Why an ORM beats raw SQL", "Type safety, relationships and automatic injection protection.", "Alice Johnson", ["orm", "database"]),
        ("Async database access in FastAPI", "Using create_async_engine and AsyncSession without blocking.", "Bob Smith", ["fastapi", "sqlalchemy"]),
        ("Understanding the N+1 problem", "Why lazy loading can quietly multiply your queries.", "Bob Smith", ["orm", "database", "tutorial"]),
        ("Alembic migrations in practice", "Autogenerate, review, upgrade and downgrade.", "Carol Danvers", ["sqlalchemy", "database"]),
        ("Connection pooling explained", "pool_size, max_overflow and pool_pre_ping.", "Carol Danvers", ["database", "sqlalchemy"]),
        ("SQLModel vs SQLAlchemy", "Typed models with a little less boilerplate.", "David Kim", ["python", "orm"]),
        ("Testing database code with pytest", "In-memory SQLite and a clean fixture per test.", "Emma Wilson", ["python", "tutorial"]),
        ("Many-to-many relationships", "Association tables, link models and tags.", "Farid Ahmadi", ["orm", "sqlalchemy"]),
        ("Transactions and rollback", "All-or-nothing writes with Session.commit and rollback.", "Grace Lee", ["database", "sqlalchemy"]),
        ("Query optimisation tips", "Indexes, selectinload and measuring SQL.", "Hassan Rezaei", ["database", "orm"]),
        ("Building a CRUD API", "Wiring SQLModel models into FastAPI routes.", "Alice Johnson", ["fastapi", "python", "tutorial"]),
    ]

    posts = []
    for title, content, author_name, tag_names in post_specs:
        post = Post(
            title=title,
            content=content,
            user_id=user_by_name[author_name].id,
        )
        post.tags = [tag_by_name[name] for name in tag_names]
        posts.append(post)

    session.add_all(posts)
    session.commit()

    return {
        "created": True,
        "message": "Demo data created.",
        "users": len(users),
        "posts": len(posts),
        "tags": len(tags),
    }
