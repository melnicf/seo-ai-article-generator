"""Central configuration for the article generation pipeline."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CLEARSCOPE_DIR = DATA_DIR / "clearscope"
SC_CACHE_DIR = DATA_DIR / "search_console"
CASE_STUDIES_CACHE = DATA_DIR / "case_studies"
ARTICLE_OUTPUT_DIR = ROOT_DIR / "output" / "articles"
TEMPLATES_DIR = DATA_DIR / "templates"

# CSV template files
KEYWORDS_CSV = TEMPLATES_DIR / "keywords.csv"
HEADERS_CSV = TEMPLATES_DIR / "headers.csv"
QUESTIONS_CSV = TEMPLATES_DIR / "questions.csv"
HIRE_PAGES_CSV = TEMPLATES_DIR / "hire_pages.csv"

# ── API Keys ───────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
SC_SITE_URL = os.getenv("SC_SITE_URL", "sc-domain:lemon.io")

# ── Claude settings ────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 16000  # ~4000 words
CLAUDE_TEMPERATURE = 0.7

# ── Article generation settings ────────────────────────────────────────────
TARGET_WORD_COUNT = 3000
MIN_CLEARSCOPE_COVERAGE = 0.90  # 90% term coverage target

# ── Internal link pool ─────────────────────────────────────────────────────
LEMON_INTERNAL_LINKS = {
    "AI engineers": "https://lemon.io/hire/ai-engineers/",
    "full-stack developers": "https://lemon.io/hire/full-stack-developers/",
    "front-end developers": "https://lemon.io/hire/front-end-developers/",
    "back-end developers": "https://lemon.io/hire/back-end-developers/",
    "mobile developers": "https://lemon.io/hire/mobile-developers/",
    "DevOps engineers": "https://lemon.io/hire/devops/",
    "app developers": "https://lemon.io/hire/app-developers/",
    "Lemon.io": "https://lemon.io/",
    "Python developers": "https://lemon.io/hire/python-developers/",
    "PHP developers": "https://lemon.io/hire/php-developers/",
    "JavaScript developers": "https://lemon.io/hire/javascript-developers/",
    "Node.js developers": "https://lemon.io/hire/node-js-developers/",
    "React developers": "https://lemon.io/hire/react-developers/",
    "Angular developers": "https://lemon.io/hire/angular-developers/",
    "Vue.js developers": "https://lemon.io/hire/vue-js-developers/",
    "Java developers": "https://lemon.io/hire/java-developers/",
    "Ruby on Rails developers": "https://lemon.io/hire/ruby-on-rails-developers/",
    ".NET developers": "https://lemon.io/hire/net-developers/",
    "Flutter developers": "https://lemon.io/hire/flutter-developers/",
    "React Native developers": "https://lemon.io/hire/react-native-developers/",
    "Django developers": "https://lemon.io/hire/django-developers/",
    "Laravel developers": "https://lemon.io/hire/laravel-developers/",
    "Next.js developers": "https://lemon.io/hire/next-js-developers/",
}
