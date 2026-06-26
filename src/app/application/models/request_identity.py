"""Request identity normalization for application use cases."""

from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class RequestIdentity:
    """Normalized request identity values.

    Attributes:
        user_id: End-user identifier, or anonymous when unavailable.
        thread_id: Conversation thread identifier.
        session_id: User session identifier.
        trace_id: Request trace identifier.
        display_name: Optional browser-stored user display name.
    """

    user_id: str
    thread_id: str
    session_id: str
    trace_id: str
    display_name: str


def new_uuid8_hex() -> str:
    """Generate a UUIDv8 hex identifier."""
    return uuid.uuid8().hex


def normalize_optional_text(value: str | None) -> str | None:
    """Return stripped text, or None when missing/blank.

    Args:
        value: Raw value from HTTP headers, query params, forms, or services.

    Returns:
        Stripped string or None.
    """
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    return normalized


def normalize_user_id(value: str | None) -> str:
    """Return a non-empty user identifier.

    Args:
        value: Optional user identifier supplied by the client.

    Returns:
        Stripped user identifier, or anonymous.
    """
    return normalize_optional_text(value) or "anonymous"


def build_request_identity(
    user_id: str | None = None,
    thread_id: str | None = None,
    session_id: str | None = None,
    trace_id: str | None = None,
    display_name: str | None = None,
) -> RequestIdentity:
    """Build mandatory request identity values.

    Args:
        user_id: Optional user ID. Defaults to anonymous when blank/missing.
        thread_id: Optional thread ID. Defaults to UUIDv8.
        session_id: Optional session ID. Defaults to UUIDv8.
        trace_id: Optional trace ID. Defaults to UUIDv8.

    Returns:
        Normalized request identity.
    """
    return RequestIdentity(
        user_id=normalize_user_id(user_id),
        thread_id=normalize_optional_text(thread_id) or new_uuid8_hex(),
        session_id=normalize_optional_text(session_id) or new_uuid8_hex(),
        trace_id=normalize_optional_text(trace_id) or new_uuid8_hex(),
        display_name=normalize_optional_text(display_name) or "",
    )
