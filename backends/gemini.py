import json
from typing import Any, Dict

from core import config, prompts
from core import schema


def _error_response(message: str) -> Dict[str, Any]:
    return {"is_valid": False, "errors": [f"Validation service error: {message}"], "warnings": []}


def validate_user_data_gemini(user_data: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
    """Validate user data via Gemini API; retries with repair prompt on bad JSON/schema."""
    config.logger.info(f"Using Gemini model: {config.GEMINI_MODEL_NAME}")
    try:
        import google.generativeai as genai
    except ImportError:
        return _error_response("google-generativeai package not installed")

    if not config.GEMINI_API_KEY:
        return _error_response("GEMINI_API_KEY environment variable not set")

    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
    except Exception as e:
        return _error_response(f"Failed to initialize Gemini client: {str(e)}")

    full_prompt = f"{prompts.SYSTEM_PROMPT}\n\nUser Input:\n{json.dumps(user_data)}"

    for attempt in range(max_retries + 1):
        config.logger.info(f"Validation attempt {attempt + 1}/{max_retries + 1}")
        try:
            response = model.generate_content(
                full_prompt,
                generation_config={"temperature": 0.0, "response_mime_type": "application/json"},
            )
            content = response.text
            if not content:
                raise ValueError("Received empty response from LLM.")

            validated_response = json.loads(content)
            is_valid, error_msg = schema.validate_schema(validated_response)
            if not is_valid:
                if attempt < max_retries:
                    full_prompt = f"{prompts.SYSTEM_PROMPT}\n\nUser Input:\n{json.dumps(user_data)}\n\n{prompts.REPAIR_PROMPT}"
                    continue
                return _error_response(error_msg)
            return validated_response

        except json.JSONDecodeError:
            if attempt < max_retries:
                full_prompt = f"{prompts.SYSTEM_PROMPT}\n\nUser Input:\n{json.dumps(user_data)}\n\n{prompts.REPAIR_PROMPT}"
                continue
            return _error_response("LLM returned malformed JSON")
        except Exception as e:
            config.logger.error(f"Exception on attempt {attempt + 1}: {str(e)}", exc_info=True)
            if attempt < max_retries:
                continue
            return _error_response(str(e))

    return _error_response("Maximum retries exceeded")
