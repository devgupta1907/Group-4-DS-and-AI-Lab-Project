"""Entry point.

    uv run uvicorn main:app --reload

The application itself is assembled in src/app.py. Nothing is mounted
here, so there is exactly one place that knows which modules exist.
"""

from src.app import create_app

app = create_app()
