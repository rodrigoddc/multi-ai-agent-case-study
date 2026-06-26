"""Architecture test: forbid SQLAlchemy/ORM usage in application layer.

This test scans src/app/application for any direct references to SQLAlchemy
or async session makers which must be contained in infrastructure adapters.
"""

from pathlib import Path


def test_no_sqlalchemy_in_application() -> None:
    forbidden = [
        "import sqlalchemy",
        "from sqlalchemy",
        "AsyncSession",
        "async_sessionmaker",
    ]
    app_dir = Path("src/app/application")
    assert app_dir.exists(), "src/app/application directory not found"

    violations: list[str] = []
    for path in app_dir.rglob("*.py"):
        text = path.read_text(encoding="utf8")
        for token in forbidden:
            if token in text:
                violations.append(f"{path}: contains '{token}'")

    assert not violations, (
        "Found ORM/SQLAlchemy usage in application layer:\n" + "\n".join(violations)
    )
