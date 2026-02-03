import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL_NAME = "llama3.1:8b"
GEMINI_MODEL_NAME = "gemini-1.5-flash"
USE_GEMINI_API = os.getenv("USE_GEMINI_API", "false").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"
LOG_FILE = ROOT_DIR / "validation.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(LOG_FILE),
    ],
)
logger = logging.getLogger(__name__)
