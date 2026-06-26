"""Architecture tests: ensure application layer doesn't import infrastructure.

This prevents accidental dependency rule violations (application -> infrastructure).
"""

from pathlib import Path


def test_application_folder_has_no_infrastructure_imports():
    app_dir = Path("src/app/application")
    assert app_dir.exists(), "src/app/application folder missing"

    violations = []
    for path in sorted(app_dir.rglob("*.py")):
        text = path.read_text(encoding="utf8")
        if "src.app.infrastructure" in text:
            violations.append(str(path))

    assert not violations, (
        f"Application layer must not import infrastructure. Violations: {violations}"
    )
