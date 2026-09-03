# DSA Roadmap

A local-first DSA learning workspace for planning practice, solving Python problems, revisiting older questions, and understanding progress over time.

## Current status

This repository contains the initial public project scaffold and product PRD. The application will be built incrementally around a complete weekly learning loop.

## Product direction

- Personal, single-user, local-first web application.
- Desktop-first solving experience.
- Django and HTMX application with SQLite persistence.
- In-app Python problem solving with saved attempts and visible tests.
- Adaptive problem reviews and weekly assessments.
- Deep attempt and mistake analysis is a later phase.

## Local setup

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

Local application data belongs in the ignored SQLite database and backup files. Do not commit personal study history, credentials, or generated catalog data.

## Planned milestones

1. Build the weekly DSA loop with six foundational topics.
2. Add the full LeetCode public catalog and synchronization.
3. Add the broader DSA curriculum, review scheduling, assessments, and analytics.
4. Explore richer attempt analysis, additional sources, and hosted deployment.

See the public GitHub issue titled **PRD: DSA Roadmap Learning Workspace** for the product requirements and implementation boundaries.
