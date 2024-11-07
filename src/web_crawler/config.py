import os
from dotenv import load_dotenv

load_dotenv()

HIGH_PRIORITY_KEYWORDS = [
    "Contact",
    "ACFR",
    "Budget",
    "Financial Report",
    "Annual Report",
    "Fiscal Year",
    "Financial Statement",
]

MEDIUM_PRIORITY_KEYWORDS = ["Finance", "Director", "Department", "Contact", "Staff", "Treasury"]

SEED_URLS = ["https://www.a2gov.org/", "https://bozeman.net/", "https://asu.edu/", "https://boerneisd.net/"]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
}

RATE_LIMIT = 1  # seconds between requests - since geminie free tier is 15 req/min

DATABASE_PATH = "hello_world.db"

# Retry settings
MAX_RETRIES = 3
BASE_DELAY = 2  # Start with 2 second delay
MAX_DELAY = 30  # Never wait more than 30 seconds


# Crawler settings
MAX_DEPTH = 2
MAX_TOTAL_PAGES = 10
MAX_LINKS_PER_PAGE = 50
TEST_MODE = True
GEMINI_BATCH_SIZE = 10

# Test mode settings - see Makefile / README for command to run in test mode
TEST_MODE = True
TEST_URLS = ["https://bozeman.net/"]
TEST_MAX_LINKS = 5
TEST_MAX_TOTAL_PAGES = 5
TEST_BATCH_SIZE = 5
TEST_MAX_DEPTH = 1
