"""
Entry point for the web crawler.
Run with: python -m src.web_crawler [--high-priority word1,word2] [--medium-priority word3,word4]
"""

import logging
import argparse
import sys
from .crawler import Crawler
from .database import Database
from .utils import parse_keywords
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
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

        # Crawl each test URL
        for url in urls:
            logger.info(f"\nStarting crawl of {url}")
            try:
                result = crawler.crawl_page(
                    url=url, high_priority_keywords=high_priority, medium_priority_keywords=medium_priority
                )

                if result and "links" in result:
                    num_links = len(result["links"])
                    logger.info(f"Successfully processed {url} with {num_links} links")
                else:
                    logger.warning(f"No valid results for {url}")

            except KeyboardInterrupt:
                logger.info("\n🛑 Crawler stopped by user. Saving current progress...")
                break  # Exit cleanly from the URL loop
            except Exception as e:
                logger.error(f"Failed to process {url}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Crawler encountered a critical error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
