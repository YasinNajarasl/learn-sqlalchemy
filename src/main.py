"""FastAPI application and HTTP routes for the SQLAlchemy Lab.

The routes are deliberately thin: each one delegates to a function in
:mod:`src.crud` so the presentation code stays easy to follow.
"""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from sqlmodel.ext.asyncio.session import AsyncSession

from . import crud, events  # noqa: F401  (events registers ORM listeners)
from .course import workbook
from .brand import BANNER
from .course_fa import localize
from .lab import run_lab, schema_snapshot
from .database import (
    clear_event_log,
    clear_sql_log,
    engine,
    get_async_session,
    get_event_log,
    get_pool_status,
    get_session,
    get_sql_log,
    init_db,
    reset_db,
)
from .models import (
    AgeUpdateRequest,
    AtomicTransactionRequest,
    BulkInsertRequest,
    PostCreate,
    PostRead,
    PostWithAuthor,
    RollbackRequest,
    TagCreate,
    TagRead,
    TagWithCount,
    UserCreate,
    UserRead,
    UserWithPosts,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
AUTO_SEED = os.getenv("AUTO_SEED", "true").lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.getLogger("uvicorn.error").info("%s", BANNER)
    init_db()
    if AUTO_SEED:
        with Session(engine) as session:
            crud.seed_demo_data(session)
    yield


app = FastAPI(
    title="Yasin’s SQLAlchemy Lab",
    contact={"name": "Yasin"},
    description=(
        "A runnable companion to the 45-slide SQLAlchemy / SQLModel tutorial. "
        "Every endpoint maps to a slide and is exercised by the web UI."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
@app.exception_handler(IntegrityError)
async def integrity_error_handler(_request: Request, _exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": (
                "Database constraint violated. A record with the same unique "
                "value may already exist."
            )
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# UI + health
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "database": engine.url.render_as_string(hide_password=True),
    }


@app.get("/learn/workbook")
def course_material(lang: str = "en"):
    course = workbook()
    return localize(course) if lang == "fa" else course


class LabRunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    live: bool = False


def _require_local(request: Request) -> None:
    if os.getenv("LAB_ENABLED", "true").lower() in {"0", "false", "no", "off"}:
        raise HTTPException(status_code=403, detail="The code lab is disabled.")
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost", "testclient"}:
        raise HTTPException(
            status_code=403,
            detail="The code lab only accepts requests from this machine.",
        )


@app.post("/lab/run")
def lab_run(payload: LabRunRequest, request: Request):
    _require_local(request)
    try:
        return run_lab(payload.code, live=payload.live)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/lab/schema")
def lab_schema(request: Request):
    _require_local(request)
    return schema_snapshot()


# ---------------------------------------------------------------------------
# Users — slides 17–23, 26, 29, 35
# ---------------------------------------------------------------------------
@app.post("/users/", response_model=UserRead)
def api_create_user(
    user: UserCreate, session: Session = Depends(get_session)
):
    return crud.create_user(session, user)


@app.post("/users/bulk/")
def api_mass_insert_users(
    count: int = Query(100, ge=1, le=5000),
    session: Session = Depends(get_session),
):
    inserted = crud.mass_insert_users(session, count=count)
    return {"inserted": inserted}


@app.get("/users/", response_model=List[UserRead])
def api_list_users(
    response: Response,
    limit: int = Query(10, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = None,
    min_age: Optional[int] = Query(None, ge=0, le=150),
    max_age: Optional[int] = Query(None, ge=0, le=150),
    email_domain: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc",
    session: Session = Depends(get_session),
):
    users, total = crud.list_users_filtered(
        session,
        q=q,
        min_age=min_age,
        max_age=max_age,
        email_domain=email_domain,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return users


@app.get("/users/by-name/{name}", response_model=UserRead)
def api_get_user_by_name(name: str, session: Session = Depends(get_session)):
    user = crud.get_user_by_name(session, name)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/{user_id}", response_model=UserRead)
def api_get_user(user_id: int, session: Session = Depends(get_session)):
    user = crud.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/{user_id}/posts-summary")
def api_user_with_posts(
    user_id: int, session: Session = Depends(get_session)
):
    data = crud.get_user_with_posts(session, user_id)
    if not data:
        raise HTTPException(status_code=404, detail="User not found")
    return data


@app.get("/users/{user_id}/eager", response_model=UserWithPosts)
def api_user_eager(user_id: int, session: Session = Depends(get_session)):
    user = crud.get_user_eager(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/{user_id}/async")
async def api_async_user(
    user_id: int, async_session: AsyncSession = Depends(get_async_session)
):
    user = await crud.async_get_user_with_posts(async_session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "age": user.age,
        "posts": [
            {
                "id": post.id,
                "title": post.title,
                "tags": [tag.name for tag in post.tags],
            }
            for post in user.posts
        ],
    }


@app.patch("/users/{user_id}/age", response_model=UserRead)
def api_update_user_age(
    user_id: int,
    new_age: int = Query(..., ge=1, le=150),
    session: Session = Depends(get_session),
):
    user = crud.update_user_age(session, user_id, new_age)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/users/bulk/increment-age")
def api_mass_update_ages(session: Session = Depends(get_session)):
    updated = crud.mass_increment_user_ages(session)
    return {"updated_users": updated}


@app.delete("/users/{user_id}")
def api_delete_user(user_id: int, session: Session = Depends(get_session)):
    deleted = crud.delete_user(session, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Posts — slides 14, 23, 26, 30
# ---------------------------------------------------------------------------
@app.post("/posts/", response_model=PostRead)
def api_create_post(
    post: PostCreate, session: Session = Depends(get_session)
):
    return crud.create_post(session, post)


@app.get("/posts/", response_model=List[PostWithAuthor])
def api_list_posts(
    response: Response,
    limit: int = Query(10, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = None,
    user_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    sort_by: str = "created_at",
    order: str = "desc",
    session: Session = Depends(get_session),
):
    posts, total = crud.list_posts_filtered(
        session,
        q=q,
        user_id=user_id,
        tag_id=tag_id,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return posts


@app.get("/posts/with-users/")
def api_posts_with_users(
    min_age: int = Query(20, ge=0, le=150),
    session: Session = Depends(get_session),
):
    pairs = crud.get_posts_with_users(session, min_age=min_age)
    return [
        {
            "post_id": post.id,
            "title": post.title,
            "author": user.name,
            "age": user.age,
        }
        for post, user in pairs
    ]


@app.get("/posts/{post_id}", response_model=PostWithAuthor)
def api_get_post(post_id: int, session: Session = Depends(get_session)):
    post = crud.get_post(session, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.delete("/posts/bulk/by-author-age")
def api_mass_delete_posts(
    age_threshold: int = Query(30, ge=0, le=150),
    session: Session = Depends(get_session),
):
    deleted_count = crud.mass_delete_posts_by_author_age(
        session, age_threshold
    )
    return {"deleted_posts": deleted_count}


@app.delete("/posts/{post_id}")
def api_delete_post(post_id: int, session: Session = Depends(get_session)):
    deleted = crud.delete_post(session, post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"deleted": True}


@app.post("/posts/{post_id}/tags/{tag_id}", response_model=PostWithAuthor)
def api_attach_tag(
    post_id: int, tag_id: int, session: Session = Depends(get_session)
):
    post = crud.attach_tag(session, post_id, tag_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post or tag not found")
    return post


@app.delete("/posts/{post_id}/tags/{tag_id}", response_model=PostWithAuthor)
def api_detach_tag(
    post_id: int, tag_id: int, session: Session = Depends(get_session)
):
    post = crud.detach_tag(session, post_id, tag_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post or tag not found")
    return post


# ---------------------------------------------------------------------------
# Tags — slide 27
# ---------------------------------------------------------------------------
@app.post("/tags/", response_model=TagRead)
def api_create_tag(tag: TagCreate, session: Session = Depends(get_session)):
    return crud.create_tag(session, tag)


@app.get("/tags/", response_model=List[TagWithCount])
def api_list_tags(session: Session = Depends(get_session)):
    return crud.list_tags(session)


@app.delete("/tags/{tag_id}")
def api_delete_tag(tag_id: int, session: Session = Depends(get_session)):
    deleted = crud.delete_tag(session, tag_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Statistics — slides 31 and 12C
# ---------------------------------------------------------------------------
@app.get("/stats/user-ages")
def api_user_age_stats(session: Session = Depends(get_session)):
    return crud.get_user_age_stats(session)


@app.get("/stats/posts-per-user")
def api_posts_per_user(session: Session = Depends(get_session)):
    return crud.get_posts_per_user(session)


@app.get("/stats/overview")
def api_overview(session: Session = Depends(get_session)):
    return crud.get_overview(session)


# ---------------------------------------------------------------------------
# Transactions and loading demos — slides 29 and 32
# ---------------------------------------------------------------------------
@app.post("/transactions/update-age-and-publish")
def api_atomic_transaction(
    payload: AtomicTransactionRequest,
    session: Session = Depends(get_session),
):
    post = crud.update_age_and_publish_post(
        session,
        user_id=payload.user_id,
        new_age=payload.new_age,
        title=payload.title,
        content=payload.content,
    )
    return {
        "committed": True,
        "user_id": payload.user_id,
        "new_age": payload.new_age,
        "post_id": post.id,
        "title": post.title,
    }


@app.post("/transactions/rollback-demo")
def api_rollback_demo(
    payload: RollbackRequest, session: Session = Depends(get_session)
):
    return crud.transaction_rollback_demo(
        session, user_id=payload.user_id, new_age=payload.new_age
    )


@app.get("/relationships/loading-demo")
def api_loading_demo(session: Session = Depends(get_session)):
    return crud.loading_strategy_demo(session)


# ---------------------------------------------------------------------------
# Debug / observability — slides 8, 36 and 37
# ---------------------------------------------------------------------------
@app.get("/debug/sql-log")
def api_sql_log(limit: int = Query(100, ge=1, le=300)):
    return get_sql_log(limit=limit)


@app.delete("/debug/sql-log")
def api_clear_sql_log():
    clear_sql_log()
    return {"cleared": True}


@app.get("/debug/events")
def api_event_log(limit: int = Query(100, ge=1, le=200)):
    return get_event_log(limit=limit)


@app.delete("/debug/events")
def api_clear_event_log():
    clear_event_log()
    return {"cleared": True}


@app.get("/debug/pool")
def api_pool_status():
    return get_pool_status()


# ---------------------------------------------------------------------------
# Demo controls
# ---------------------------------------------------------------------------
@app.post("/demo/seed")
def api_seed(session: Session = Depends(get_session)):
    return crud.seed_demo_data(session)


@app.post("/demo/reset")
def api_reset(seed: bool = Query(True)):
    reset_db()
    if seed:
        with Session(engine) as session:
            result = crud.seed_demo_data(session)
        return {"reset": True, "seeded": True, "seed_result": result}
    return {"reset": True, "seeded": False}
