"""SQLModel models and API schemas.

Slides 9–14 define the declarative base, the User model, column types,
constraints/indexes and the Post model with a foreign key.  SQLModel is
SQLAlchemy's typed, Pydantic-aware layer, so the same ideas apply with a
little less boilerplate.
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import EmailStr
from sqlalchemy import CheckConstraint, Column, Index, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    """Naive UTC timestamp (the same value the slides get from utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Slide 9/10 — User model
# ---------------------------------------------------------------------------
class UserBase(SQLModel):
    name: str = Field(max_length=100, index=True)
    email: EmailStr = Field(unique=True, index=True)
    age: int = Field(gt=0, le=150, description="Age must be a positive integer")
    bio: Optional[str] = Field(default=None, max_length=300)


class User(UserBase, table=True):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_name_email", "name", "email"),
        UniqueConstraint("name", "email", name="uq_users_name_email"),
        CheckConstraint("age >= 0", name="ck_users_age_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)

    # Slide 25 — one-to-many with cascade delete.
    posts: List["Post"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: int
    created_at: datetime


class UserUpdate(SQLModel):
    name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    age: Optional[int] = Field(default=None, gt=0, le=150)
    bio: Optional[str] = Field(default=None, max_length=300)


# ---------------------------------------------------------------------------
# Slide 14 — Post model and foreign key
# ---------------------------------------------------------------------------
class PostBase(SQLModel):
    title: str = Field(max_length=200, index=True)
    content: str = Field(sa_column=Column(Text, nullable=False))


# Slide 27 — many-to-many association table.  It is declared before the two
# related models so the typed ``link_model=PostTag`` reference can be used.
class PostTag(SQLModel, table=True):
    __tablename__ = "post_tags"

    post_id: Optional[int] = Field(
        default=None, foreign_key="posts.id", primary_key=True
    )
    tag_id: Optional[int] = Field(
        default=None, foreign_key="tags.id", primary_key=True
    )


class Post(PostBase, table=True):
    __tablename__ = "posts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)

    author: Optional[User] = Relationship(back_populates="posts")
    tags: List["Tag"] = Relationship(back_populates="posts", link_model=PostTag)


class Tag(SQLModel, table=True):
    __tablename__ = "tags"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=50)

    posts: List[Post] = Relationship(back_populates="tags", link_model=PostTag)


class TagCreate(SQLModel):
    name: str = Field(min_length=1, max_length=50)


class TagRead(SQLModel):
    id: int
    name: str


class TagWithCount(TagRead):
    post_count: int = 0


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------
class PostCreate(PostBase):
    user_id: int
    tag_ids: List[int] = Field(default_factory=list)


class PostRead(PostBase):
    id: int
    user_id: int
    created_at: datetime
    tags: List[TagRead] = Field(default_factory=list)


class PostWithAuthor(PostRead):
    author: Optional[UserRead] = None


class UserWithPosts(UserRead):
    posts: List[PostRead] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request bodies used by the interactive demo
# ---------------------------------------------------------------------------
class AtomicTransactionRequest(SQLModel):
    user_id: int
    new_age: int = Field(ge=1, le=150)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class RollbackRequest(SQLModel):
    user_id: int
    new_age: int = Field(ge=1, le=150)


class BulkInsertRequest(SQLModel):
    count: int = Field(default=100, ge=1, le=5000)


class AgeUpdateRequest(SQLModel):
    new_age: int = Field(ge=1, le=150)


# Resolve the forward references between User, Post and Tag.
User.model_rebuild()
Post.model_rebuild()
Tag.model_rebuild()
PostTag.model_rebuild()
