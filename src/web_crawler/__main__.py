"""
Entry point for the web crawler.
Run with: python -m src.web_crawler [--high-priority word1,word2] [--medium-priority word3,word4]
"""

import logging
import argparse
import sys
from .crawler import Crawler
from .database import Database
from .utils import normalize_url, parse_keywords
from . import config

# Set the basic configuration to DEBUG level
logging.basicConfig(
    level=logging.DEBUG,  # This will show both DEBUG and INFO messages
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# No need to set individual loggers if you want all of them to show DEBUG level
logger = logging.getLogger(__name__)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Web crawler for finding relevant documents")
    parser.add_argument("--high-priority", type=str, default="", help="Comma-separated list of high priority keywords")
    parser.add_argument(
        "--medium-priority", type=str, default="", help="Comma-separated list of medium priority keywords"
    )
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    return parser.parse_args()


def main():
    """Main entry point for the crawler."""
    args = parse_arguments()

    # Set test mode and choose URLs
    if args.test:
        logger.info("🧪 TEST MODE ACTIVATED")
        urls = config.TEST_URLS
    else:
        logger.info("🚀 PRODUCTION MODE")
        urls = config.SEED_URLS

    # Parse keywords from CLI or use config defaults
    high_priority = parse_keywords(args.high_priority) or config.HIGH_PRIORITY_KEYWORDS
    medium_priority = parse_keywords(args.medium_priority) or config.MEDIUM_PRIORITY_KEYWORDS

    try:
        # Initialize database
        db = Database(config.DATABASE_PATH)
        logger.info(f"Crawler initialized with database: {config.DATABASE_PATH}")

        # Initialize crawler - test mode is passed in via CLI but defaults to False
        crawler = Crawler(db, test_mode=args.test)

        # Add debug logging to see the keywords
        logger.info(f"High priority keywords: {high_priority}")
        logger.info(f"Medium priority keywords: {medium_priority}")

        # Crawl each test URL
        for url in urls:
            # Normalize the URL first
            normalized_url = normalize_url(url)
            if not normalized_url:
                logger.error(f"Invalid URL format: {url}")
                continue

            logger.info(f"\nStarting crawl of {normalized_url}")
            result = crawler.crawl_page(
                normalized_url,
                high_priority_keywords=high_priority,  # Use parsed keywords here
                medium_priority_keywords=medium_priority,  # Use parsed keywords here
            )

            if result:
                logger.info(f"Successfully crawled {normalized_url}")
            else:
                logger.warning(f"No valid results for {normalized_url}")

    except Exception as e:
        logger.error(f"Crawler encountered a critical error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
