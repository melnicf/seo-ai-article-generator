"""Central configuration for the article generation pipeline."""

import warnings

# Suppress noisy third-party warnings (Python 3.9 EOL, OpenSSL/LibreSSL)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="google")

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
CLAUDE_MODEL = "claude-opus-4-6"
CLAUDE_MAX_TOKENS = 16000  # ~4000 words
CLAUDE_TEMPERATURE = 0.7
SELECTOR_MODEL = "claude-haiku-4-5-20251001"  # fast model for header selection
RESEARCHER_MODEL = "claude-sonnet-4-5-20250929"  # research step (web search)

# ── Google Sheets ─────────────────────────────────────────────────────────
SHEETS_SPREADSHEET_ID = os.getenv("SHEETS_SPREADSHEET_ID", "")

# ── Clearscope ───────────────────────────────────────────────────────────
CLEARSCOPE_DRAFT_URL = os.getenv("CLEARSCOPE_DRAFT_URL", "")
CLEARSCOPE_WORKSPACE = os.getenv("CLEARSCOPE_WORKSPACE", "lemon-io")

# ── Web search settings ───────────────────────────────────────────────────
WEB_SEARCH_ENABLED = True
WEB_SEARCH_MAX_USES = 3  # max searches per research request (keeps research brief lean; article max 6 external links)

# ── Article generation settings ────────────────────────────────────────────
TARGET_WORD_COUNT = 3000
MIN_CLEARSCOPE_COVERAGE = 0.90  # 90% term coverage target
EXTERNAL_LINKS_MAX = 6  # article must have 2-3 external links, never more than 6

# ── Suggested external links (official docs/sites) per technology ──────────
# Key = tech name lowercase (as from extract_tech_from_url). Model MUST include 2-3 external links; these make it easy.
TECH_OFFICIAL_LINKS = {
    "python": [
        ("Python", "https://www.python.org/"),
        ("Python documentation", "https://docs.python.org/"),
        ("PyPI", "https://pypi.org/"),
        ("Django", "https://www.djangoproject.com/"),
        ("Flask", "https://flask.palletsprojects.com/"),
        ("FastAPI", "https://fastapi.tiangolo.com/"),
    ],
    "react": [
        ("React", "https://react.dev/"),
        ("React documentation", "https://react.dev/learn"),
        ("React Native", "https://reactnative.dev/"),
        ("Next.js", "https://nextjs.org/"),
    ],
    "node.js": [
        ("Node.js", "https://nodejs.org/"),
        ("Node.js documentation", "https://nodejs.org/docs/"),
        ("npm", "https://www.npmjs.com/"),
        ("Express", "https://expressjs.com/"),
    ],
    "java": [
        ("Java", "https://www.oracle.com/java/"),
        ("Java documentation", "https://docs.oracle.com/en/java/"),
        ("Spring", "https://spring.io/"),
        ("Maven", "https://maven.apache.org/"),
    ],
    "app": [
        ("Apple Developer", "https://developer.apple.com/"),
        ("Android Developers", "https://developer.android.com/"),
        ("React Native", "https://reactnative.dev/"),
        ("Flutter", "https://flutter.dev/"),
    ],
    "javascript": [
        ("JavaScript", "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
        ("MDN Web Docs", "https://developer.mozilla.org/"),
        ("Node.js", "https://nodejs.org/"),
    ],
    "typescript": [
        ("TypeScript", "https://www.typescriptlang.org/"),
        ("TypeScript handbook", "https://www.typescriptlang.org/docs/"),
    ],
    "vue.js": [
        ("Vue.js", "https://vuejs.org/"),
        ("Vue documentation", "https://vuejs.org/guide/"),
    ],
    "angular": [
        ("Angular", "https://angular.io/"),
        ("Angular documentation", "https://angular.io/docs"),
    ],
    "php": [
        ("PHP", "https://www.php.net/"),
        ("PHP documentation", "https://www.php.net/docs.php"),
        ("Laravel", "https://laravel.com/"),
    ],
    "ruby on rails": [
        ("Ruby", "https://www.ruby-lang.org/"),
        ("Ruby on Rails", "https://rubyonrails.org/"),
        ("Rails guides", "https://guides.rubyonrails.org/"),
    ],
    "net": [
        (".NET", "https://dotnet.microsoft.com/"),
        (".NET documentation", "https://learn.microsoft.com/en-us/dotnet/"),
    ],
    "flutter": [
        ("Flutter", "https://flutter.dev/"),
        ("Flutter documentation", "https://docs.flutter.dev/"),
        ("Dart", "https://dart.dev/"),
    ],
    "react native": [
        ("React Native", "https://reactnative.dev/"),
        ("React Native documentation", "https://reactnative.dev/docs/getting-started"),
    ],
    "django": [
        ("Django", "https://www.djangoproject.com/"),
        ("Django documentation", "https://docs.djangoproject.com/"),
    ],
    "laravel": [
        ("Laravel", "https://laravel.com/"),
        ("Laravel documentation", "https://laravel.com/docs"),
    ],
    "next.js": [
        ("Next.js", "https://nextjs.org/"),
        ("Next.js documentation", "https://nextjs.org/docs"),
    ],
}

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
