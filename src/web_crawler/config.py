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

MEDIUM_PRIORITY_KEYWORDS = ["Finance", "Director", "Department", ".pdf", "Staff", "Treasury"]


SEED_URLS = ["https://www.a2gov.org/", "https://bozeman.net/", "https://asu.edu/", "https://boerneisd.net/"]


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Cache-Control": "max-age=0",
}

# update this to the filename of your db file
DATABASE_PATH = "hello_world_11_17.db"


# Crawler settings
MAX_DEPTH = 2
MAX_TOTAL_PAGES = 10
MAX_LINKS_PER_PAGE = 300
BATCH_SIZE = 20

# Test mode settings - see Makefile / README for command to run in test mode
TEST_MODE = True
TEST_URLS = ["https://www.austintexas.gov/austin-city-council"]
TEST_MAX_LINKS_PER_PAGE = 200
TEST_MAX_TOTAL_PAGES = 1
TEST_MAX_DEPTH = 1

# Retry settings
MAX_RETRIES = 3
BASE_DELAY = 2  # Start with 2 second delay
MAX_DELAY = 30  # Never wait more than 30 seconds
RATE_LIMIT = 1  # seconds between requests - since geminie free tier is 15 req/min
