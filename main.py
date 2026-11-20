from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from database import init_db, get_session, get_async_session
from models import UserCreate, UserRead, PostCreate, PostRead
import crud


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Blog App – Python ORM Deep Dive",
    description="Complete SQLModel + FastAPI walkthrough project",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/users/", response_model=UserRead)
def api_create_user(user: UserCreate, session: Session = Depends(get_session)):
    return crud.create_user(session, user)


@app.post("/users/bulk/")
def api_mass_insert_users(count: int = 100, session: Session = Depends(get_session)):
    inserted = crud.mass_insert_users(session, count=count)
    return {"inserted": inserted}


@app.get("/users/", response_model=List[UserRead])
def api_list_users(
    limit: int = 10, offset: int = 0, session: Session = Depends(get_session)
):
    return crud.list_users(session, limit=limit, offset=offset)


@app.get("/users/by-name/{name}", response_model=UserRead)
def api_get_user_by_name(name: str, session: Session = Depends(get_session)):
    user = crud.get_user_by_name(session, name)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/{user_id}/posts-summary")
def api_user_with_posts(user_id: int, session: Session = Depends(get_session)):
    data = crud.get_user_with_posts(session, user_id)
    if not data:
        raise HTTPException(status_code=404, detail="User not found")
    return data


@app.get("/users/{user_id}/async")
async def api_async_user(
    user_id: int, async_session: AsyncSession = Depends(get_async_session)
):
    user = await crud.async_get_user_with_posts(async_session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "name": user.name, "posts": user.posts}


@app.patch("/users/{user_id}/age", response_model=UserRead)
def api_update_user_age(
    user_id: int, new_age: int, session: Session = Depends(get_session)
):
    user = crud.update_user_age(session, user_id, new_age)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/users/bulk/increment-age")
def api_mass_update_ages(session: Session = Depends(get_session)):
    updated = crud.mass_increment_user_ages(session)
    return {"updated_users": updated}


@app.post("/posts/", response_model=PostRead)
def api_create_post(post: PostCreate, session: Session = Depends(get_session)):
    return crud.create_post(session, post)


@app.get("/posts/with-users/")
def api_posts_with_users(min_age: int = 20, session: Session = Depends(get_session)):
    pairs = crud.get_posts_with_users(session, min_age=min_age)
    return [
        {"post_id": post.id, "title": post.title, "author": user.name, "age": user.age}
        for post, user in pairs
    ]


@app.delete("/posts/{post_id}")
def api_delete_post(post_id: int, session: Session = Depends(get_session)):
    deleted = crud.delete_post(session, post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"deleted": True}


@app.delete("/posts/bulk/by-author-age")
def api_mass_delete_posts(
    age_threshold: int = 30, session: Session = Depends(get_session)
):
    deleted_count = crud.mass_delete_posts_by_author_age(session, age_threshold)
    return {"deleted_posts": deleted_count}


@app.get("/stats/user-ages")
def api_user_age_stats(session: Session = Depends(get_session)):
    return crud.get_user_age_stats(session)