from datetime import datetime
from typing import Optional, List
from pydantic import EmailStr
from sqlmodel import SQLModel, Field, Relationship


class UserBase(SQLModel):
    name: str = Field(max_length=100, index=True)
    email: EmailStr = Field(unique=True, index=True)
    age: int = Field(gt=0, description="Age must be a positive integer")
    bio: Optional[str] = Field(default=None, max_length=300)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # One-to-Many relationship with Post
    posts: List["Post"] = Relationship(back_populates="author")


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: int
    created_at: datetime


class PostBase(SQLModel):
    title: str = Field(max_length=200, index=True)
    content: str


class Post(PostBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Many-to-One relationship back to User
    author: Optional[User] = Relationship(back_populates="posts")


class PostCreate(PostBase):
    user_id: int


class PostRead(PostBase):
    id: int
    user_id: int
    created_at: datetime