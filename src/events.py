"""ORM event listeners from slide 37.

The listeners do two things:

* stamp ``created_at`` before a User row is inserted;
* publish a small event to the UI whenever a Session commits.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlmodel import Session

from .database import record_event
from .models import User, utcnow


@event.listens_for(User, "before_insert")
def receive_before_insert(_mapper, _connection, target: User) -> None:
    if target.created_at is None:
        target.created_at = utcnow()
    record_event("before_insert", f"User(name={target.name!r}) is being inserted")


@event.listens_for(User, "after_insert")
def receive_after_insert(_mapper, _connection, target: User) -> None:
    record_event("after_insert", f"User(id={target.id}, name={target.name!r}) inserted")


@event.listens_for(Session, "after_commit")
def receive_after_commit(session: Session) -> None:
    record_event("after_commit", "Session committed successfully")


@event.listens_for(Session, "after_rollback")
def receive_after_rollback(session: Session) -> None:
    record_event("after_rollback", "Session rolled back")
