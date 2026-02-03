import json
from typing import Any, Dict

from openai import OpenAI

from core import config, prompts
from core import schema


def _error_response(message: str) -> Dict[str, Any]:
    return {"is_valid": False, "errors": [f"Validation service error: {message}"], "warnings": []}


def validate_user_data_ollama(user_data: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
    """Validate user data via local Ollama; retries with repair prompt on bad JSON/schema."""
    config.logger.info(f"Using Ollama model: {config.OLLAMA_MODEL_NAME}")
    try:
        client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            timeout=30.0,
        )
    except Exception as e:
        config.logger.error(f"Failed to initialize Ollama client: {str(e)}")
        return _error_response(f"Failed to initialize Ollama client: {str(e)}")

    messages = [
        {"role": "system", "content": prompts.SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_data)},
    ]

    for attempt in range(max_retries + 1):
        config.logger.info(f"Validation attempt {attempt + 1}/{max_retries + 1}")
        try:
            completion = client.chat.completions.create(
                model=config.OLLAMA_MODEL_NAME,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=200,
            )
            content = completion.choices[0].message.content
            if not content:
                raise ValueError("Received empty response from LLM.")

            validated_response = json.loads(content)
            is_valid, error_msg = schema.validate_schema(validated_response)
            if not is_valid:
                if attempt < max_retries:
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": prompts.REPAIR_PROMPT})
                    continue
                return _error_response(error_msg)
            return validated_response

        except json.JSONDecodeError:
            if attempt < max_retries:
                messages.append({"role": "user", "content": prompts.REPAIR_PROMPT})
                continue
            return _error_response("LLM returned malformed JSON")
        except Exception as e:
            config.logger.error(f"Exception on attempt {attempt + 1}: {str(e)}", exc_info=True)
            if attempt < max_retries:
                continue
            return _error_response(str(e))

    return _error_response("Maximum retries exceeded")
