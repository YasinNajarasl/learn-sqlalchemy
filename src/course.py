"""Course metadata and the editable workbook shown on the Learn page."""

import ast
from pathlib import Path
from textwrap import dedent

CATEGORY_ORDER = [
    "Foundations",
    "CRUD",
    "Relationships",
    "Queries",
    "Transactions",
    "Async",
    "Capstone",
]

META = {
    1: dict(
        category="Foundations",
        level="Beginner",
        minutes=8,
        goal="Open a connection and run a parameterised SELECT.",
        hint='Use conn.execute(text("... :minimum"), {"minimum": 20}).scalars().',
    ),
    2: dict(
        category="Foundations",
        level="Beginner",
        minutes=10,
        goal="Read the schema SQLAlchemy created from the mapped classes.",
        hint='inspect(engine).get_columns("users") returns dicts with a "name" key.',
    ),
    3: dict(
        category="Foundations",
        level="Beginner",
        minutes=12,
        goal="Watch an object move from pending to persistent.",
        hint="s.add(user) makes it pending; s.flush() sends the INSERT and assigns an id.",
    ),
    4: dict(
        category="CRUD",
        level="Beginner",
        minutes=10,
        goal="Insert many rows with Core insert() and a list of mappings.",
        hint="Pass insert(User) and a list of dicts to s.execute(); include created_at.",
    ),
    5: dict(
        category="CRUD",
        level="Beginner",
        minutes=10,
        goal="Build a filtered, ordered, paginated SELECT.",
        hint="Filter to Alice and Bob, then chain .order_by(), .limit() and .offset().",
    ),
    6: dict(
        category="CRUD",
        level="Intermediate",
        minutes=12,
        goal="Update one object and delete a post without breaking foreign keys.",
        hint="Delete post_tags rows for post 1 before deleting the post itself.",
    ),
    7: dict(
        category="Relationships",
        level="Intermediate",
        minutes=14,
        goal="Create an author-post-tag graph without managing foreign keys by hand.",
        hint="Post needs title and content; pass tags=[Tag(name='sql')].",
    ),
    8: dict(
        category="Relationships",
        level="Advanced",
        minutes=15,
        goal="Measure N+1 queries and remove them with selectinload.",
        hint="Count before_cursor_execute events and use a fresh Session per strategy.",
    ),
    9: dict(
        category="Queries",
        level="Intermediate",
        minutes=12,
        goal="Join, group and count while keeping authors with zero posts.",
        hint="outerjoin(User.posts) keeps Bob if he has no posts; filter to Alice and Bob.",
    ),
    10: dict(
        category="Transactions",
        level="Advanced",
        minutes=15,
        goal="Prove that a failed multi-write transaction rolls back.",
        hint="Duplicate alice@example.com; catch IntegrityError outside the begin() block.",
    ),
    11: dict(
        category="Async",
        level="Advanced",
        minutes=18,
        goal="Run the same ORM patterns on an async engine.",
        hint="Create tables with await conn.run_sync(Base.metadata.create_all).",
    ),
    12: dict(
        category="Capstone",
        level="Advanced",
        minutes=20,
        goal="Write a tested publish function and verify it from a second session.",
        hint="Alice starts with three posts; assert that 'Transactions' is present.",
    ),
}

STARTERS = {
    1: '''
with engine.connect() as conn:
    # TODO: select Alice and Bob, filtered by a :minimum age parameter.
    # Print their names separated by commas.
    ...
''',
    2: '''
columns = inspect(engine).get_columns("users")
# TODO: print a comma-separated list of column names.
...
''',
    3: '''
with Session(engine) as s, s.begin():
    user = User(name="Cam", email="cam@example.org", age=24)
    # TODO: add the user, print pending, flush, then print persistent and bool(user.id).
    ...
''',
    4: '''
with Session(engine) as s, s.begin():
    emails = [f"u{i}@example.org" for i in range(3)]
    # TODO: insert three users with one execute(insert(User), [...]) call.
    # Include created_at=utcnow(), then print how many of those emails exist.
    ...
''',
    5: '''
stmt = (
    select(User)
    # TODO: filter to Alice and Bob, order by age descending with id as a
    # tie breaker, and keep only the first row.
)
with Session(engine) as s:
    print(s.scalars(stmt).one().name)
''',
    6: '''
with Session(engine) as s, s.begin():
    # TODO: set user 1's age to 31, delete post 1's post_tags rows,
    # then delete post 1.
    ...
with Session(engine) as s:
    print(
        s.execute(
            select(User.name, User.age)
            .where(User.email.in_(["alice@example.com", "bob@example.com"]))
            .order_by(User.id)
        ).all()
    )
''',
    7: '''
with Session(engine) as s, s.begin():
    alice = s.get(User, 1)
    # TODO: create a Post titled "Joins" with content and a new Tag "sql",
    # append it to alice.posts, flush, then print author, title and tag.
    ...
''',
    8: '''
queries = []
# TODO: register a before_cursor_execute listener that appends SELECT statements.
authors = select(User).where(User.email.in_(["alice@example.com", "bob@example.com"]))
for label, stmt in [
    ("lazy", authors),
    ("eager", authors.options(selectinload(User.posts))),
]:
    # TODO: use a fresh Session, clear queries, traverse author.posts,
    # then print the label and the number of SELECT statements.
    ...
# TODO: remove the listener.
''',
    9: '''
stmt = (
    select(User.name, func.count(Post.id))
    # TODO: filter to Alice and Bob, outer join posts, group by user,
    # and order by user id.
)
with Session(engine) as s:
    print(s.execute(stmt).all())
''',
    10: '''
try:
    with Session(engine) as s, s.begin():
        s.execute(update(User).where(User.id == 1).values(age=99))
        s.add(User(name="Duplicate", age=19, email="alice@example.com"))
except IntegrityError:
    print("rolled back")
# TODO: open a fresh Session and print user 1's age.
''',
    11: '''
async def main():
    db = create_async_engine("sqlite+aiosqlite://")
    # TODO: create tables, insert "Dee", then select and print the name.
    ...
    await db.dispose()

asyncio.run(main())
''',
    12: '''
def publish(s, email, title):
    # TODO: find the user by email, append a Post with content,
    # and let the caller commit.
    ...

with Session(engine) as s, s.begin():
    publish(s, "alice@example.com", "Transactions")
with Session(engine) as s:
    # TODO: load Alice with selectinload(User.posts), assert that
    # "Transactions" is present, and print how many posts she has.
    ...
''',
}


def workbook() -> dict:
    lines = (Path(__file__).parent / "static/workbook.py").read_text().splitlines()
    source = "\n".join(lines)
    lessons = []
    setup = ""
    for node in ast.parse(source).body:
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("lesson_")):
            continue
        number = len(lessons) + 1
        heading, explanation, exercise, output = ast.get_docstring(node).splitlines()
        title, slides = heading.split(" | ")
        if number == 1:
            setup = "\n".join(lines[: node.lineno - 1]).strip()
        lessons.append(
            {
                "number": number,
                "title": title,
                "slides": slides,
                "explanation": explanation,
                "exercise": exercise,
                "output": output.replace(" / ", "\n"),
                "code": dedent("\n".join(lines[node.body[0].end_lineno : node.end_lineno])),
                "starter": dedent(STARTERS[number]).strip(),
                **META[number],
            }
        )
    categories = [
        {
            "name": category,
            "lessons": [lesson["number"] for lesson in lessons if lesson["category"] == category],
        }
        for category in CATEGORY_ORDER
    ]
    return {"setup": setup, "lessons": lessons, "categories": categories}
