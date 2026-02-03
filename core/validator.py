from typing import Any, Dict

from backends import gemini, ollama

from . import config


def validate_user_data(user_data: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
    """Validate user data via Ollama or Gemini depending on env; single entry for callers."""
    if config.USE_GEMINI_API:
        config.logger.info("Using Gemini API for validation")
        return gemini.validate_user_data_gemini(user_data, max_retries)
    config.logger.info("Using Ollama (local) for validation")
    return ollama.validate_user_data_ollama(user_data, max_retries)
