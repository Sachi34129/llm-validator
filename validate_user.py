import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),  # Log to stderr so stdout is clean JSON
        logging.FileHandler('validation.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
OLLAMA_MODEL_NAME = "llama3.1:8b"  # Using local Ollama model
GEMINI_MODEL_NAME = "gemini-1.5-flash"  # Gemini model

# Environment variables
USE_GEMINI_API = os.getenv("USE_GEMINI_API", "false").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
PROMPTS_DIR = SCRIPT_DIR / "prompts"

def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = PROMPTS_DIR / filename
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        logger.info(f"Loaded prompt from {prompt_path}")
        return content
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {prompt_path}")
        raise
    except Exception as e:
        logger.error(f"Error loading prompt file {prompt_path}: {str(e)}")
        raise

# Load prompts
try:
    SYSTEM_PROMPT = load_prompt("system_prompt.txt")
    REPAIR_PROMPT = load_prompt("repair_prompt.txt")
except Exception as e:
    logger.error(f"Failed to load prompts: {str(e)}")
    sys.exit(1)

def validate_schema(response: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate that response matches expected schema exactly.
    Returns (is_valid, error_message)
    """
    logger.debug("Validating response schema")
    
    # Check for required fields
    required_fields = ["is_valid", "errors", "warnings"]
    if not all(field in response for field in required_fields):
        missing = [f for f in required_fields if f not in response]
        error_msg = f"Missing required fields: {missing}"
        logger.warning(f"Schema validation failed: {error_msg}")
        return False, error_msg
    
    # Check for extra fields (schema drift)
    extra_fields = [k for k in response.keys() if k not in required_fields]
    if extra_fields:
        error_msg = f"Extra fields not allowed: {extra_fields}"
        logger.warning(f"Schema validation failed: {error_msg}")
        return False, error_msg
    
    # Check types
    if not isinstance(response["is_valid"], bool):
        error_msg = "is_valid must be boolean"
        logger.warning(f"Schema validation failed: {error_msg}")
        return False, error_msg
    if not isinstance(response["errors"], list):
        error_msg = "errors must be array"
        logger.warning(f"Schema validation failed: {error_msg}")
        return False, error_msg
    if not isinstance(response["warnings"], list):
        error_msg = "warnings must be array"
        logger.warning(f"Schema validation failed: {error_msg}")
        return False, error_msg
    
    # Check that arrays contain only strings
    if not all(isinstance(e, str) for e in response["errors"]):
        error_msg = "errors must contain only strings"
        logger.warning(f"Schema validation failed: {error_msg}")
        return False, error_msg
    if not all(isinstance(w, str) for w in response["warnings"]):
        error_msg = "warnings must contain only strings"
        logger.warning(f"Schema validation failed: {error_msg}")
        return False, error_msg
    
    logger.debug("Schema validation passed")
    return True, ""

def validate_user_data_ollama(user_data: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
    """
    Validates user data using Ollama (local LLM) with retry logic and schema enforcement.
    
    Args:
        user_data: User profile dictionary to validate
        max_retries: Maximum number of retry attempts for malformed responses
        
    Returns:
        Validated response matching schema or fallback error response
    """
    logger.info(f"Using Ollama model: {OLLAMA_MODEL_NAME}")
    
    # Use local Ollama instance
    try:
        client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",  # required, but unused
            timeout=30.0,  # 30 second timeout to prevent hanging
        )
        logger.debug("Ollama client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Ollama client: {str(e)}")
        return {
            "is_valid": False,
            "errors": [f"Validation service error: Failed to initialize Ollama client: {str(e)}"],
            "warnings": []
        }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_data)}
    ]
    
    logger.info(f"Starting validation with {max_retries + 1} max attempts")
    logger.debug(f"Input data: {json.dumps(user_data)}")
    
    for attempt in range(max_retries + 1):
        logger.info(f"Validation attempt {attempt + 1}/{max_retries + 1}")
        try:
            logger.debug(f"Sending request to Ollama model: {OLLAMA_MODEL_NAME}")
            completion = client.chat.completions.create(
                model=OLLAMA_MODEL_NAME,
                messages=messages,
                response_format={"type": "json_object"},  # Enforce JSON output
                temperature=0.0,  # Deterministic output for consistency
                max_tokens=200,  # Limit output tokens for faster response (JSON is small)
            )
            
            content = completion.choices[0].message.content
            logger.debug(f"Received response from LLM (length: {len(content) if content else 0})")
            
            if not content:
                raise ValueError("Received empty response from LLM.")
            
            logger.debug(f"Raw LLM response: {content[:200]}...")  # Log first 200 chars
            
            validated_response = json.loads(content)
            logger.debug("Successfully parsed JSON from LLM response")
            
            # Validate schema strictly
            is_valid, error_msg = validate_schema(validated_response)
            if not is_valid:
                if attempt < max_retries:
                    logger.warning(f"Schema validation failed on attempt {attempt + 1}: {error_msg}")
                    logger.info("Retrying with repair prompt...")
                    # Repair loop: re-prompt with schema violation message
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": REPAIR_PROMPT})
                    continue
                else:
                    # Last attempt failed, return error
                    logger.error(f"Schema validation failed on final attempt: {error_msg}")
                    return {
                        "is_valid": False,
                        "errors": [f"Validation service error: {error_msg}"],
                        "warnings": []
                    }
            
            logger.info("Validation successful")
            logger.debug(f"Final validated response: {json.dumps(validated_response)}")
            return validated_response

        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries:
                logger.info("Retrying with repair prompt...")
                # Repair loop for JSON errors
                messages.append({"role": "user", "content": REPAIR_PROMPT})
                continue
            logger.error("JSON decode error on final attempt")
            return {
                "is_valid": False,
                "errors": ["Validation service error: LLM returned malformed JSON"],
                "warnings": []
            }
        except Exception as e:
            logger.error(f"Exception on attempt {attempt + 1}: {str(e)}", exc_info=True)
            if attempt < max_retries:
                logger.info("Retrying...")
                continue
            return {
                "is_valid": False,
                "errors": [f"Validation service error: {str(e)}"],
                "warnings": []
            }
    
    # Should never reach here, but provide fallback
    logger.error("Maximum retries exceeded")
    return {
        "is_valid": False,
        "errors": ["Validation service error: Maximum retries exceeded"],
        "warnings": []
    }

def validate_user_data_gemini(user_data: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
    """
    Validates user data using Gemini API with retry logic and schema enforcement.
    
    Args:
        user_data: User profile dictionary to validate
        max_retries: Maximum number of retry attempts for malformed responses
        
    Returns:
        Validated response matching schema or fallback error response
    """
    logger.info(f"Using Gemini model: {GEMINI_MODEL_NAME}")
    
    try:
        import google.generativeai as genai
        logger.debug("Successfully imported google.generativeai")
    except ImportError:
        logger.error("google-generativeai package not installed")
        return {
            "is_valid": False,
            "errors": ["Validation service error: google-generativeai package not installed"],
            "warnings": []
        }
    
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY environment variable not set")
        return {
            "is_valid": False,
            "errors": ["Validation service error: GEMINI_API_KEY environment variable not set"],
            "warnings": []
        }
    
    # Configure Gemini
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        logger.debug("Gemini client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {str(e)}")
        return {
            "is_valid": False,
            "errors": [f"Validation service error: Failed to initialize Gemini client: {str(e)}"],
            "warnings": []
        }
    
    # Build the prompt
    full_prompt = f"{SYSTEM_PROMPT}\n\nUser Input:\n{json.dumps(user_data)}"
    
    logger.info(f"Starting validation with {max_retries + 1} max attempts")
    logger.debug(f"Input data: {json.dumps(user_data)}")
    
    for attempt in range(max_retries + 1):
        logger.info(f"Validation attempt {attempt + 1}/{max_retries + 1}")
        try:
            # Generate content with JSON response format
            generation_config = {
                "temperature": 0.0,
                "response_mime_type": "application/json",
            }
            
            logger.debug(f"Sending request to Gemini model: {GEMINI_MODEL_NAME}")
            response = model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            content = response.text
            logger.debug(f"Received response from LLM (length: {len(content) if content else 0})")
            
            if not content:
                raise ValueError("Received empty response from LLM.")
            
            logger.debug(f"Raw LLM response: {content[:200]}...")  # Log first 200 chars
            
            validated_response = json.loads(content)
            logger.debug("Successfully parsed JSON from LLM response")
            
            # Validate schema strictly
            is_valid, error_msg = validate_schema(validated_response)
            if not is_valid:
                if attempt < max_retries:
                    logger.warning(f"Schema validation failed on attempt {attempt + 1}: {error_msg}")
                    logger.info("Retrying with repair prompt...")
                    # Repair loop: re-prompt with schema violation message
                    full_prompt = f"{SYSTEM_PROMPT}\n\nUser Input:\n{json.dumps(user_data)}\n\n{REPAIR_PROMPT}"
                    continue
                else:
                    # Last attempt failed, return error
                    logger.error(f"Schema validation failed on final attempt: {error_msg}")
                    return {
                        "is_valid": False,
                        "errors": [f"Validation service error: {error_msg}"],
                        "warnings": []
                    }
            
            logger.info("Validation successful")
            logger.debug(f"Final validated response: {json.dumps(validated_response)}")
            return validated_response

        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries:
                logger.info("Retrying with repair prompt...")
                # Repair loop for JSON errors
                full_prompt = f"{SYSTEM_PROMPT}\n\nUser Input:\n{json.dumps(user_data)}\n\n{REPAIR_PROMPT}"
                continue
            logger.error("JSON decode error on final attempt")
            return {
                "is_valid": False,
                "errors": ["Validation service error: LLM returned malformed JSON"],
                "warnings": []
            }
        except Exception as e:
            logger.error(f"Exception on attempt {attempt + 1}: {str(e)}", exc_info=True)
            if attempt < max_retries:
                logger.info("Retrying...")
                continue
            return {
                "is_valid": False,
                "errors": [f"Validation service error: {str(e)}"],
                "warnings": []
            }
    
    # Should never reach here, but provide fallback
    logger.error("Maximum retries exceeded")
    return {
        "is_valid": False,
        "errors": ["Validation service error: Maximum retries exceeded"],
        "warnings": []
    }

def validate_user_data(user_data: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
    """
    Validates user data using an LLM with retry logic and schema enforcement.
    Chooses between Ollama (local) and Gemini API based on environment variables.
    
    Args:
        user_data: User profile dictionary to validate
        max_retries: Maximum number of retry attempts for malformed responses
        
    Returns:
        Validated response matching schema or fallback error response
    """
    if USE_GEMINI_API:
        logger.info("Using Gemini API for validation")
        return validate_user_data_gemini(user_data, max_retries)
    else:
        logger.info("Using Ollama (local) for validation")
        return validate_user_data_ollama(user_data, max_retries)

def main():
    parser = argparse.ArgumentParser(description="Validate user profile JSON using LLM.")
    parser.add_argument("input_file", help="Path to the JSON file containing user data.")
    args = parser.parse_args()

    logger.info(f"Starting validation for file: {args.input_file}")
    logger.info(f"LLM Provider: {'Gemini API' if USE_GEMINI_API else 'Ollama (local)'}")

    # Read input file
    try:
        with open(args.input_file, 'r') as f:
            user_data = json.load(f)
        logger.debug(f"Successfully loaded input file: {args.input_file}")
    except FileNotFoundError:
        logger.error(f"Input file not found: {args.input_file}")
        print(json.dumps({
            "is_valid": False,
            "errors": [f"Input file not found: {args.input_file}"],
            "warnings": []
        }, indent=2))
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Input file contains invalid JSON: {args.input_file}, error: {str(e)}")
        print(json.dumps({
            "is_valid": False,
            "errors": [f"Input file contains invalid JSON: {args.input_file}"],
            "warnings": []
        }, indent=2))
        sys.exit(1)

    # Validate
    logger.info("Starting validation process")
    result = validate_user_data(user_data)
    logger.info("Validation process completed")

    # Output result
    print(json.dumps(result, indent=2))
    logger.info("Output sent to stdout")

if __name__ == "__main__":
    main()
