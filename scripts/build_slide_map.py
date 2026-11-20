"""Refresh the Learn page data and README references from the bundled deck."""
import ast
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

root = Path(__file__).resolve().parents[1]
ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
# Conceptual slides point to a representative implementation where applicable.
refs = """
Introduction|-
Roadmap|-
Objects and tables|models User
Why SQLAlchemy?|-
Raw SQL comparison|crud get_user_age_stats
Architecture|main api_create_user
Install dependencies|requirements.txt
Engine|database engine
Declarative base (SQLModel adaptation)|models UserBase
User model|models User
Column types (examples in use)|models UserBase
Keys, constraints and indexes|models User
Create tables|database init_db
Post and foreign key|models Post
Session|database get_session
Object lifecycle (insert example)|crud create_user
Insert|crud create_user
Bulk insert|crud mass_insert_users
Select|crud get_user_by_name
Filter|crud list_users_filtered
Sort and paginate|crud list_users_filtered
Update|crud update_user_age
Delete|crud delete_post
Relationship types (implemented examples)|models Post
One-to-many|models User
Traverse relationships|crud get_user_with_posts
Many-to-many association|models PostTag
Loading strategies compared|crud loading_strategy_demo
Eager loading|crud get_user_eager
Join|crud get_posts_with_users
Group and count|crud get_posts_per_user
Commit or roll back|crud transaction_rollback_demo
Alembic metadata|alembic/env.py target_metadata
Migration workflow|alembic/versions/24b470064191_initial_schema.py upgrade
Async session query|crud async_get_user_with_posts
Connection pool settings|database engine
ORM event listener|events receive_before_insert
Test fixture|tests/test_blog.py session_fixture
Common mistakes (N+1 example)|crud loading_strategy_demo
Project layout|-
Web request and dependency|main api_create_user
Best practices (session scope)|database get_session
CRUD cheat sheet (insert example)|crud create_user
Further reading|-
Closing slide|-
""".strip().splitlines()
rows, links = [], []
with ZipFile(root / "SQLAlchemy_Full_Tutorial_FA.pptx") as deck:
    for n, ref in enumerate(refs, 1):
        title, loc = ref.split("|")
        slide = ET.fromstring(deck.read(f"ppt/slides/slide{n}.xml"))
        blocks = ["\n".join("".join(p.itertext()) for p in shape.findall("a:p", ns))
                  for shape in slide.findall(".//p:sp/p:txBody", ns)]
        row = dict(slide=n, title=title, text="\n\n".join(filter(str.strip, blocks)))
        target = "Presentation only"
        if loc != "-":
            path, *symbols = loc.split()
            if "." not in path:
                path = f"src/{path}.py"
            source = (root / path).read_text()
            start, end = 1, len(source.splitlines())
            if symbols:
                node = next(x for x in ast.parse(source).body
                            if getattr(x, "name", None) == symbols[0] or
                            any(getattr(t, "id", None) == symbols[0] for t in getattr(x, "targets", [])))
                start, end = node.lineno, node.end_lineno
            row.update(file=path, symbol=" ".join(symbols), start=start, end=end)
            target = f"[`/{path}#L{start}-L{end}`]({path}#L{start}-L{end})"
        rows.append(row)
        links.append(f"- slide {n} -> {target} — {title}")
(root / "src/static/slide_map.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
readme = root / "README.md"
marker = "<!-- generated slide references -->"
readme.write_text(readme.read_text().split(marker)[0] + marker + "\n\n" + "\n".join(links) + "\n")
