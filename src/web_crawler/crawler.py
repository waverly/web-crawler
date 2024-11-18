"""
Web crawler for government websites.
Crawls pages and extracts relevant links based on content analysis.
"""

import certifi
from typing import Dict, List, Optional, Set
import logging
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from .database import Database
from .open_ai_analyzer import analyze_page_content
from .utils import exponential_backoff, extract_links
from . import config

logger = logging.getLogger(__name__)


class Crawler:
    def __init__(self, db: Database, test_mode: bool = False) -> None:
        """Initialize crawler with database connection and configuration."""
        self.db = db
        self.visited_urls: Set[str] = set()
        self.session = self._init_session()
        self.test_mode = test_mode
        self.max_links = config.TEST_MAX_LINKS_PER_PAGE if test_mode else config.MAX_LINKS_PER_PAGE
        self.max_depth = config.TEST_MAX_DEPTH if test_mode else config.MAX_DEPTH
        self._set_mode_configuration()

    def _init_session(self) -> requests.Session:
        """Initialize and configure the HTTP session."""
        session = requests.Session()
        session.headers.update(config.HEADERS)
        return session

    def _set_mode_configuration(self) -> None:
        """Set crawler configuration based on the mode (test or production)."""
        mode = "Test" if self.test_mode else "Production"
        logger.info(f"🐍 {mode} mode active.")

        # Assign configuration based on mode
        if self.test_mode:
            self.urls = config.TEST_URLS
            self.max_links = config.TEST_MAX_LINKS_PER_PAGE
            self.max_pages = config.TEST_MAX_TOTAL_PAGES
            self.max_depth = config.TEST_MAX_DEPTH
            self.batch_size = config.BATCH_SIZE
        else:
            self.urls = config.SEED_URLS
            self.max_links = config.MAX_LINKS_PER_PAGE
            self.max_pages = config.MAX_TOTAL_PAGES
            self.max_depth = config.MAX_DEPTH
            self.batch_size = config.BATCH_SIZE

        # Log configuration
        logger.info(f"  URLs: {self.urls}")
        logger.info(f"  Max links per page: {self.max_links}")
        logger.info(f"  Max total pages: {self.max_pages}")
        logger.info(f"  Max depth: {self.max_depth}")
        logger.info(f"  Batch size: {self.batch_size}")

    @exponential_backoff(max_retries=3, base_delay=2.0)
    def _fetch_page(self, url: str) -> Optional[requests.Response]:
        """Fetch a page from the web with retries and error handling."""
        logger.debug(f"Attempting to fetch URL: {url}")

        try:
            response = self.session.get(url, timeout=20, allow_redirects=True, verify=certifi.where())
            content_type = response.headers.get("content-type", "").lower()

            if not content_type.startswith("text/html"):
                logger.warning(f"Skipping non-HTML content: {content_type} at {url}")
                return None

            logger.info(f"Successfully fetched page: {url}")
            logger.info(f"Response : {response}")
            return response

        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            raise

    def crawl(self) -> None:
        """Initiate crawling process for all seed URLs."""
        for url in self.urls:
            self.crawl_page(
                url,
                high_priority_keywords=config.HIGH_PRIORITY_KEYWORDS,
                medium_priority_keywords=config.MEDIUM_PRIORITY_KEYWORDS,
            )

    def crawl_page(
        self,
        url: str,
        high_priority_keywords: List[str],
        medium_priority_keywords: List[str],
        current_depth: int = 0,
    ) -> Optional[Dict]:
        """Crawl a single page and process its links."""
        if current_depth > self.max_depth:
            logger.debug(f"Skipping {url} as it exceeds max depth {self.max_depth}")
            return

        if url in self.visited_urls:
            logger.info(f"URL already visited: {url}")
            return None

        logger.info(f"Starting crawl for URL: {url} at depth {current_depth}")
        logger.debug(f"Current Depth: {current_depth}, Max Depth: {self.max_depth}")

        # Early validation of URL format
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            logger.info(f"Invalid URL format: {url}")
            return None

        try:
            logger.info(f"Attempting to fetch URL: {url}")
            response = self._fetch_page(url)
            logger.info(f"Fetched response: {response}")
            if not response:
                return None
        except Exception as e:
            logger.info(f"Failed to fetch page {url} after retries: {e}")
            return None

        # Attempt to store the page and retrieve its ID
        page_id = self.db.store_page(url)
        if not page_id:
            logger.info(f"Could not store or retrieve page ID for {url}")
            return None

        self.visited_urls.add(url)

        # Parse the HTML content
        soup = self._parse_html(response, url)
        if not soup:
            return None

        # Extract links from the parsed HTML
        raw_links = extract_links(soup, url)
        self._log_extracted_links(raw_links)

        # Limit the number of links if in test mode
        if self.test_mode:
            raw_links = self._limit_links_for_test_mode(raw_links)

        # Filter out links that have already been analyzed
        new_links = self._filter_new_links(raw_links)
        if not new_links:
            logger.info("No new links to analyze.")
            return {"url": url, "num_links": 0, "links": []}

        # **Limit to the first MAX_LINKS_PER_PAGE links**
        limited_new_links = new_links[: self.max_links]
        logger.info(f"Processing {len(limited_new_links)} links out of {len(new_links)} extracted links.")

        # Format links for analysis
        links_with_context = self._format_links_for_analysis(limited_new_links)
        logger.info(f"Formatted links: {links_with_context}")

        # Analyze the new links using OpenAI
        analyzed_links = self._analyze_links(links_with_context, high_priority_keywords, medium_priority_keywords)
        if not analyzed_links:
            logger.info("No links analyzed as relevant.")
            return None

        logger.info(f"Analyzed links: {analyzed_links}")

        try:
            # Store the analyzed links in the database
            formatted_links = self._format_links_for_db(analyzed_links)
            logger.info(f"Formatted links for DB: {formatted_links}")
            self.db.store_links(formatted_links, page_id)
            logger.info(f"Stored page {url} with ID {page_id} and {len(analyzed_links)} links.")
        except Exception as e:
            logger.error(f"Error processing links for page {url}: {e}")
            return None

        # **Check if current_depth is less than max_depth before crawling child links**
        if current_depth < self.max_depth:
            logger.info(f"Crawling child links at depth {current_depth + 1}")
            self._crawl_child_links(analyzed_links, high_priority_keywords, medium_priority_keywords, current_depth + 1)
        else:
            logger.info(f"Max depth reached at URL: {url}")

        return {"url": url, "num_links": len(analyzed_links), "links": analyzed_links}

    def _has_reached_page_limit(self) -> bool:
        """Check if the crawler has reached the maximum number of pages."""
        if len(self.visited_urls) >= self.max_pages:
            logger.info(f"Reached max total pages: {self.max_pages}")
            return True
        return False

    def _parse_html(self, response: requests.Response, url: str) -> Optional[BeautifulSoup]:
        """Parse HTML content using BeautifulSoup."""
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            logger.debug(f"Parsed HTML for URL: {url}")
            return soup
        except Exception as e:
            logger.error(f"HTML parsing error for {url}: {e}")
            return None

    def _log_extracted_links(self, raw_links: List[Dict]) -> None:
        """Log the extracted links for debugging."""
        logger.debug(f"Extracted {len(raw_links)} links from the page.")
        # if logger.isEnabledFor(logging.DEBUG):
        #     for link in raw_links:
        #         logger.debug(f"Extracted link: {link}")

    def _limit_links_for_test_mode(self, raw_links: List[Dict]) -> List[Dict]:
        """Limit the number of links processed in test mode."""
        if len(raw_links) > self.max_links:
            logger.info(f"🧪 Test mode: Limiting links from {len(raw_links)} to {self.max_links}.")
            return raw_links[: self.max_links]
        return raw_links

    def _filter_new_links(self, raw_links: List[Dict]) -> List[Dict]:
        """Filter out links that have already been analyzed and stored."""
        urls_to_check = [link["url"] for link in raw_links]
        existing_urls = self.db.get_existing_urls(urls_to_check)
        new_links = [link for link in raw_links if link["url"] not in existing_urls]
        return new_links

    def _format_links_for_analysis(self, links: List[Dict]) -> List[Dict]:
        """Format links for analysis."""
        return [
            {
                "url": link.get("url"),
                "link_text": link.get("link_text", ""),
                "context": link.get("context", ""),
            }
            for link in links
        ]

    def _analyze_links(
        self,
        links_with_context: List[Dict],
        high_priority_keywords: List[str],
        medium_priority_keywords: List[str],
    ) -> List[Dict]:
        """Analyze new links using Gemini API."""
        logger.info(f"🤖 Analyzing {len(links_with_context)} new links with OpenAI.")
        analyzed_links = analyze_page_content(
            links_with_context,
            high_priority_keywords,
            medium_priority_keywords,
            test_mode=self.test_mode,
        )
        if analyzed_links:
            logger.info(f"✅ Successfully analyzed {len(analyzed_links)} relevant links.")
        else:
            logger.info("No links analyzed as relevant.")
        return analyzed_links

    def _format_links_for_db(self, analyzed_links: List[Dict]) -> List[Dict]:
        """Prepare analyzed links for database insertion."""

        def _clean_keywords(keywords):
            if isinstance(keywords, str):
                # Split the string on commas if it's a comma-separated string
                return [kw.strip() for kw in keywords.split(",")]
            elif isinstance(keywords, list):
                return [str(kw).strip() for kw in keywords if kw]
            else:
                return []

        formatted = []
        for link in analyzed_links:
            high_priority = _clean_keywords(link.get("high_priority_keywords", []))
            medium_priority = _clean_keywords(link.get("medium_priority_keywords", []))

            formatted_link = {
                "url": link["url"],
                "relevancy": link.get("relevancy", 0.0),
                "relevancy_explanation": link.get("relevancy_explanation", ""),
                "high_priority_keywords": high_priority,  # Don't join here
                "medium_priority_keywords": medium_priority,  # Don't join here
                "context": link.get("context", ""),
            }

            formatted.append(formatted_link)
        return formatted

    def get_existing_urls(self, urls: List[str]) -> Set[str]:
        """
        Check which URLs from the provided list already exist in the database.

        Args:
            urls (List[str]): A list of URLs to check.

        Returns:
            Set[str]: A set of URLs that already exist in the database.
        """
        if not urls:
            return set()

        # Assuming you have a table named 'pages' with a 'url' column
        query = """
            SELECT url FROM pages WHERE url IN (%s)
        """ % ", ".join(
            ["%s"] * len(urls)
        )

        cursor = self.connection.cursor()
        cursor.execute(query, urls)
        results = cursor.fetchall()
        cursor.close()

        # Extract URLs from query results
        existing_urls = set(row[0] for row in results)
        return existing_urls

    def _crawl_child_links(
        self,
        analyzed_links: List[Dict],
        high_priority_keywords: List[str],
        medium_priority_keywords: List[str],
        current_depth: int,
    ) -> None:
        """Recursively crawl child links with incremented depth."""
        for link in analyzed_links:
            child_url = link.get("url")
            if not child_url or not isinstance(child_url, str):
                logger.debug(f"Invalid child URL: {child_url}")
                continue
            self.crawl_page(
                url=child_url,
                high_priority_keywords=high_priority_keywords,
                medium_priority_keywords=medium_priority_keywords,
                current_depth=current_depth + 1,
            )
