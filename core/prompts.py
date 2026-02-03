import sys

from . import config


def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = config.PROMPTS_DIR / filename
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        config.logger.info(f"Loaded prompt from {prompt_path}")
        return content
    except FileNotFoundError:
        config.logger.error(f"Prompt file not found: {prompt_path}")
        raise
    except Exception as e:
        config.logger.error(f"Error loading prompt file {prompt_path}: {str(e)}")
        raise


try:
    SYSTEM_PROMPT = load_prompt("system_prompt.txt")
    REPAIR_PROMPT = load_prompt("repair_prompt.txt")
except Exception as e:
    config.logger.error(f"Failed to load prompts: {str(e)}")
    sys.exit(1)
