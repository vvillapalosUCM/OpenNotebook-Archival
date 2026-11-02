"""
Detection of placeholder and well-known weak secrets.

The API refuses to start when OPEN_NOTEBOOK_PASSWORD or
OPEN_NOTEBOOK_ENCRYPTION_KEY still holds a value copied from a template or
from the documentation, because anyone who has read this repository knows it.

Classification works on a normalised form (lower case, letters and digits
only), so "CHANGE_ME", "change-me" and "⚠️_CAMBIAR_ESTO_..." are all caught.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

SecretIssue = Literal["placeholder", "weak", "short"]

MIN_RECOMMENDED_LENGTH = 12

# Substrings that only appear in template values ("CHANGE_ME_TO_...",
# "⚠️_CAMBIAR_ESTO_...", "your-secret-key", "my-secret-passphrase"...).
_PLACEHOLDER_MARKERS = (
    "changeme",
    "changethis",
    "cambiaresto",
    "cambiame",
    "replaceme",
    "yoursecret",
    "yoursecure",
    "yourstrong",
    "yourpassword",
    "yourkey",
    "mysecret",
    "mydevsecret",
)

# Exact values that appear as examples in this repository's docs and
# templates, normalised.
_DOCUMENTED_EXAMPLES = frozenset(
    {
        "opennotebookchangeme",
        "mysecure2024researchtool",
        "notebookdev2024strong",
        "securepassword",
    }
)

# Common weak values, normalised.
_WEAK_VALUES = frozenset(
    {
        "root",
        "admin",
        "administrator",
        "password",
        "password1",
        "password123",
        "passw0rd",
        "secret",
        "opennotebook",
        "notebook",
        "test",
        "demo",
        "default",
        "letmein",
        "qwerty",
        "123456",
        "12345678",
        "123456789",
    }
)


def _normalise(value: str) -> str:
    return re.sub(r"[^0-9a-z]", "", value.strip().lower())


def classify_secret(value: Optional[str]) -> Optional[SecretIssue]:
    """Return the problem with a secret value, or None if it looks acceptable.

    - "placeholder": copied from a template or from the documentation.
    - "weak": a well-known weak value such as "root" or "password123".
    - "short": shorter than MIN_RECOMMENDED_LENGTH characters.

    An empty or missing value returns None: "not set" is handled separately
    by the callers.
    """
    if value is None or not value.strip():
        return None
    normalised = _normalise(value)
    if normalised in _DOCUMENTED_EXAMPLES or any(
        marker in normalised for marker in _PLACEHOLDER_MARKERS
    ):
        return "placeholder"
    if normalised in _WEAK_VALUES:
        return "weak"
    if len(value.strip()) < MIN_RECOMMENDED_LENGTH:
        return "short"
    return None
