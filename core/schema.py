import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["is_valid", "errors", "warnings"]


def validate_schema(response: Dict[str, Any]) -> tuple[bool, str]:
    """Return (is_valid, error_message) for LLM response shape."""
    if not all(field in response for field in REQUIRED_FIELDS):
        missing = [f for f in REQUIRED_FIELDS if f not in response]
        msg = f"Missing required fields: {missing}"
        logger.warning(f"Schema validation failed: {msg}")
        return False, msg

    extra = [k for k in response.keys() if k not in REQUIRED_FIELDS]
    if extra:
        msg = f"Extra fields not allowed: {extra}"
        logger.warning(f"Schema validation failed: {msg}")
        return False, msg

    if not isinstance(response["is_valid"], bool):
        msg = "is_valid must be boolean"
        logger.warning(f"Schema validation failed: {msg}")
        return False, msg
    if not isinstance(response["errors"], list):
        msg = "errors must be array"
        logger.warning(f"Schema validation failed: {msg}")
        return False, msg
    if not isinstance(response["warnings"], list):
        msg = "warnings must be array"
        logger.warning(f"Schema validation failed: {msg}")
        return False, msg

    if not all(isinstance(e, str) for e in response["errors"]):
        msg = "errors must contain only strings"
        logger.warning(f"Schema validation failed: {msg}")
        return False, msg
    if not all(isinstance(w, str) for w in response["warnings"]):
        msg = "warnings must contain only strings"
        logger.warning(f"Schema validation failed: {msg}")
        return False, msg

    return True, ""
