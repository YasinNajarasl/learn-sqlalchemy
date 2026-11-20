# Yasin’s SQLAlchemy Lab

**English · فارسی** — Choose the interface language in the page header. Persian uses a right-to-left layout; runnable Python, SQL and query results keep their original text. Your browser remembers the language, and both editions share the same database, lesson drafts and progress. The startup console and API documentation identify the lab as Yasin’s.

A local, interactive companion to [the 45-slide SQLAlchemy tutorial](SQLAlchemy_Full_Tutorial_FA.pdf). Create a user, publish a tagged post, then inspect the SQL and ORM events produced by those actions. Changes persist in SQLite between runs.

**Copyright © 2026 Yasin. All rights reserved.** See [LICENSE](LICENSE) for reuse terms. The Vazirmatn font has its own [open font license](src/static/fonts/OFL.txt).

## Run

From this directory, with Python 3.10+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn src.main:app --reload
```

Open <http://127.0.0.1:8000/> for the UI or [/docs](http://127.0.0.1:8000/docs) for the interactive API. Use `src.main:app`; the application code lives in `src/`. No frontend build or external database service is required.

## Try a lesson

1. **Dashboard → Users:** create a user with a unique email, filter by name, then change their age. In **SQL Console**, look for `INSERT`, `SELECT` and `UPDATE`. The event feed shows when the ORM inserts a user and commits the session.
2. **Posts:** publish a post for that user and assign a tag. A post stores its author in `posts.user_id`; each tag assignment adds a row to `post_tags` rather than duplicating the post.
3. **Relationships:** compare lazy and eager loading on the seeded users. Lazy traversal can issue a separate query for each author's posts; `selectinload` fetches related rows in batches. **Analytics** shows grouped counts.
4. **Transactions:** update an age and publish a post together. Try the rollback demo, then revisit Users: flushing sent changes to SQLite, but rollback restored the original age.
5. **Learn:** follow twelve English code-along lessons. Each lab has a starter, a prediction exercise, a hint, the solution, and an editor that runs the code. The **Live lab** streams captured SQL and stdout, and the **Database explorer** shows the current tables, row counts, columns and foreign keys. Progress and drafts are saved in your browser. The migration field lab and the 45-slide index are in collapsible sections below the course.

## Code lab

The Learn editor executes Python in a separate process with a timeout, a CPU/memory limit, and an allow-list of builtins and imports. Two modes are available:

- **Practice (default):** the server takes a consistent snapshot of the current SQLite database, runs your code against the copy, and discards it. Reads and writes are safe.
- **Live database:** code runs against the real `blog.db`. A commit persists, an update changes existing rows, and a delete is permanent. The UI asks for confirmation before enabling this mode.

The allow-list is a teaching guardrail, not a security sandbox. The endpoints only accept requests from the local machine and are disabled with `LAB_ENABLED=false`. Never expose this app to a network or the internet. Set `LAB_TIMEOUT` (seconds, default `8`) to change the execution limit.

The runner exposes `engine`, `Session`, `select`, `func`, `insert`, `update`, `delete`, `text`, `inspect`, `event`, `IntegrityError`, `selectinload`, `joinedload`, `asyncio`, `create_async_engine`, `async_sessionmaker`, `Base`, `User`, `Post`, `Tag`, `PostTag`, `post_tags`, `UserCreate`, `TagCreate`, `SQLModel`, `Field`, `Relationship` and `utcnow`. Its API is `POST /lab/run` with `{"code": "...", "live": false}` and `GET /lab/schema`.

## How the app fits together

The HTML and JavaScript in [`src/static/`](src/static/) send requests to [`src/main.py`](src/main.py). FastAPI validates request bodies using schemas in [`src/models.py`](src/models.py) and obtains a request-scoped session from [`src/database.py`](src/database.py). [`src/crud.py`](src/crud.py) builds queries and commits writes; the session dependency rolls back on errors and closes the session. [`src/events.py`](src/events.py) registers listeners used by the event feed.

Startup creates missing tables in `blog.db` and seeds sample data if there are no users. `AUTO_SEED=false` disables startup seeding. The demo reset drops and recreates the lab tables. To keep a separate database, set both `DATABASE_URL=sqlite:///./my-lab.db` and `ASYNC_DATABASE_URL=sqlite+aiosqlite:///./my-lab.db` before starting the server.

## Tests and migrations

Run `python -m pytest -q` from the project root. CRUD tests use isolated sessions and API tests use a temporary SQLite file. To practice migrations on a **new** file, run `DATABASE_URL=sqlite:///./migration-lab.db python -m alembic upgrade head`. Alembic reads the model metadata and applies the checked-in revision; ordinary app startup uses `create_all`, which creates missing tables but does not migrate existing ones.

## Slide → source index

Numbers follow the [SQLAlchemy PPTX](SQLAlchemy_Full_Tutorial_FA.pptx). The paths below refer to the running implementation or its supporting tests and configuration. To refresh these line ranges and the Learn page after editing code, run `python3 scripts/build_slide_map.py`.
<!-- generated slide references -->

- slide 1 -> Presentation only — Introduction
- slide 2 -> Presentation only — Roadmap
- slide 3 -> [`/src/models.py#L32-L47`](src/models.py#L32-L47) — Objects and tables
- slide 4 -> Presentation only — Why SQLAlchemy?
- slide 5 -> [`/src/crud.py#L407-L413`](src/crud.py#L407-L413) — Raw SQL comparison
- slide 6 -> [`/src/main.py#L167-L170`](src/main.py#L167-L170) — Architecture
- slide 7 -> [`/requirements.txt#L1-L10`](requirements.txt#L1-L10) — Install dependencies
- slide 8 -> [`/src/database.py#L120-L128`](src/database.py#L120-L128) — Engine
- slide 9 -> [`/src/models.py#L25-L29`](src/models.py#L25-L29) — Declarative base (SQLModel adaptation)
- slide 10 -> [`/src/models.py#L32-L47`](src/models.py#L32-L47) — User model
- slide 11 -> [`/src/models.py#L25-L29`](src/models.py#L25-L29) — Column types (examples in use)
- slide 12 -> [`/src/models.py#L32-L47`](src/models.py#L32-L47) — Keys, constraints and indexes
- slide 13 -> [`/src/database.py#L167-L171`](src/database.py#L167-L171) — Create tables
- slide 14 -> [`/src/models.py#L87-L95`](src/models.py#L87-L95) — Post and foreign key
- slide 15 -> [`/src/database.py#L182-L189`](src/database.py#L182-L189) — Session
- slide 16 -> [`/src/crud.py#L49-L54`](src/crud.py#L49-L54) — Object lifecycle (insert example)
- slide 17 -> [`/src/crud.py#L49-L54`](src/crud.py#L49-L54) — Insert
- slide 18 -> [`/src/crud.py#L60-L76`](src/crud.py#L60-L76) — Bulk insert
- slide 19 -> [`/src/crud.py#L99-L101`](src/crud.py#L99-L101) — Select
- slide 20 -> [`/src/crud.py#L116-L160`](src/crud.py#L116-L160) — Filter
- slide 21 -> [`/src/crud.py#L116-L160`](src/crud.py#L116-L160) — Sort and paginate
- slide 22 -> [`/src/crud.py#L181-L190`](src/crud.py#L181-L190) — Update
- slide 23 -> [`/src/crud.py#L204-L211`](src/crud.py#L204-L211) — Delete
- slide 24 -> [`/src/models.py#L87-L95`](src/models.py#L87-L95) — Relationship types (implemented examples)
- slide 25 -> [`/src/models.py#L32-L47`](src/models.py#L32-L47) — One-to-many
- slide 26 -> [`/src/crud.py#L244-L252`](src/crud.py#L244-L252) — Traverse relationships
- slide 27 -> [`/src/models.py#L76-L84`](src/models.py#L76-L84) — Many-to-many association
- slide 28 -> [`/src/crud.py#L474-L498`](src/crud.py#L474-L498) — Loading strategies compared
- slide 29 -> [`/src/crud.py#L255-L261`](src/crud.py#L255-L261) — Eager loading
- slide 30 -> [`/src/crud.py#L166-L175`](src/crud.py#L166-L175) — Join
- slide 31 -> [`/src/crud.py#L393-L404`](src/crud.py#L393-L404) — Group and count
- slide 32 -> [`/src/crud.py#L433-L468`](src/crud.py#L433-L468) — Commit or roll back
- slide 33 -> [`/alembic/env.py#L28-L28`](alembic/env.py#L28-L28) — Alembic metadata
- slide 34 -> [`/alembic/versions/24b470064191_initial_schema.py#L22-L69`](alembic/versions/24b470064191_initial_schema.py#L22-L69) — Migration workflow
- slide 35 -> [`/src/crud.py#L504-L513`](src/crud.py#L504-L513) — Async session query
- slide 36 -> [`/src/database.py#L120-L128`](src/database.py#L120-L128) — Connection pool settings
- slide 37 -> [`/src/events.py#L19-L22`](src/events.py#L19-L22) — ORM event listener
- slide 38 -> [`/tests/test_blog.py#L15-L31`](tests/test_blog.py#L15-L31) — Test fixture
- slide 39 -> [`/src/crud.py#L474-L498`](src/crud.py#L474-L498) — Common mistakes (N+1 example)
- slide 40 -> Presentation only — Project layout
- slide 41 -> [`/src/main.py#L167-L170`](src/main.py#L167-L170) — Web request and dependency
- slide 42 -> [`/src/database.py#L182-L189`](src/database.py#L182-L189) — Best practices (session scope)
- slide 43 -> [`/src/crud.py#L49-L54`](src/crud.py#L49-L54) — CRUD cheat sheet (insert example)
- slide 44 -> Presentation only — Further reading
- slide 45 -> Presentation only — Closing slide
