from collections.abc import Mapping
from typing import Any


_PRIVATE_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "jwt",
        "access_token",
        "refresh_token",
        "phone",
        "email",
        "service_role_key",
        "supabase_service_role_key",
        "storage_url",
        "public_url",
        "private_url",
        "evidence_url",
        "image_url",
        "file_url",
        "storage_path",
        "latitude",
        "longitude",
        "working_latitude",
        "working_longitude",
    }
)


def public_payload(values: Mapping[str, Any]) -> dict[str, Any]:
    """Keep realtime payloads minimal and exclude credentials/private media fields."""
    return {
        key: _sanitize(value)
        for key, value in values.items()
        if key.lower() not in _PRIVATE_KEYS
    }


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return public_payload(value)
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize(item) for item in value)
    return value