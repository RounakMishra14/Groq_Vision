import os
from dotenv import load_dotenv

load_dotenv()

# =========================
# API Configuration
# =========================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"

# =========================
# Application Settings
# =========================

MAX_IMAGES = 30

# Delay between requests
# Helps avoid rate limits
DELAY_SECONDS = 3

# =========================
# PDF Settings
# =========================

DEFAULT_PDF_NAME = "Extracted_MCQs"

PDF_THEMES = [
    "Light",
    "Dark"
]