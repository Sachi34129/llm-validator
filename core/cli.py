import argparse
import json
import sys

from . import config, validator


def main() -> None:
    """Parse args, read JSON file, run validator, print result to stdout."""
    parser = argparse.ArgumentParser(description="Validate user profile JSON using LLM.")
    parser.add_argument("input_file", help="Path to the JSON file containing user data.")
    args = parser.parse_args()

    config.logger.info(f"Starting validation for file: {args.input_file}")
    config.logger.info(f"LLM Provider: {'Gemini API' if config.USE_GEMINI_API else 'Ollama (local)'}")

    try:
        with open(args.input_file, "r") as f:
            user_data = json.load(f)
    except FileNotFoundError:
        config.logger.error(f"Input file not found: {args.input_file}")
        print(
            json.dumps(
                {
                    "is_valid": False,
                    "errors": [f"Input file not found: {args.input_file}"],
                    "warnings": [],
                },
                indent=2,
            )
        )
        sys.exit(1)
    except json.JSONDecodeError as e:
        config.logger.error(f"Input file contains invalid JSON: {args.input_file}, error: {str(e)}")
        print(
            json.dumps(
                {
                    "is_valid": False,
                    "errors": [f"Input file contains invalid JSON: {args.input_file}"],
                    "warnings": [],
                },
                indent=2,
            )
        )
        sys.exit(1)

    config.logger.info("Starting validation process")
    result = validator.validate_user_data(user_data)
    config.logger.info("Validation process completed")

    print(json.dumps(result, indent=2))
    config.logger.info("Output sent to stdout")
