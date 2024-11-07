"""
Web crawler for government websites.
Crawls pages and extracts relevant links based on content analysis.
"""

from typing import Dict, List, Optional, Set
import logging
import requests
from bs4 import BeautifulSoup
from .database import Database
from .gemini_analyzer import analyze_page_content
from .utils import exponential_backoff, normalize_url, extract_links
from . import config

logger = logging.getLogger(__name__)


class Crawler:
    def __init__(self, db: Database, test_mode: bool = False) -> None:
        """Initialize crawler with database connection and configuration."""
        self.db = db
        self.visited_urls: Set[str] = set()
        self.session = self._init_session()
        self.test_mode = test_mode
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
            self.max_links = config.TEST_MAX_LINKS
            self.max_pages = config.TEST_MAX_TOTAL_PAGES
            self.max_depth = config.TEST_MAX_DEPTH
            self.batch_size = config.TEST_BATCH_SIZE
        else:
            self.urls = config.SEED_URLS
            self.max_links = config.MAX_LINKS_PER_PAGE
            self.max_pages = config.MAX_TOTAL_PAGES
            self.max_depth = config.MAX_DEPTH
            self.batch_size = config.GEMINI_BATCH_SIZE

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

        normalized_url = normalize_url(url)
        if not normalized_url:
            logger.error(f"Normalization failed for URL: {url}")
            return None

        if normalized_url in self.visited_urls:
            logger.debug(f"URL already visited: {normalized_url}")
            return None

        try:
            response = self.session.get(normalized_url, timeout=20, allow_redirects=True)
            content_type = response.headers.get("content-type", "").lower()

            if not content_type.startswith("text/html"):
                logger.warning(f"Skipping non-HTML content: {content_type} at {normalized_url}")
                return None

            logger.info(f"Successfully fetched page: {normalized_url}")
            return response

        except requests.RequestException as e:
            logger.error(f"Error fetching URL {normalized_url}: {e}")
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
        self, url: str, high_priority_keywords: List[str], medium_priority_keywords: List[str], current_depth: int = 0
    ) -> Optional[Dict]:
        """Crawl a single page and process its links."""
        logger.debug(f"Starting crawl for URL: {url} at depth {current_depth}")

        if not self._is_valid_depth(current_depth) or self._has_reached_page_limit():
            return None

        response = self._fetch_page(url)
        if not response:
            return None

        normalized_url = normalize_url(url)
        if not normalized_url:
            logger.error(f"Normalization failed for URL: {url}")
            return None

        # Attempt to store the page and retrieve its ID
        page_id = self.db.store_page(normalized_url)
        if not page_id:
            logger.error(f"Could not store or retrieve page ID for {normalized_url}")
            return None

        # Mark the URL as visited only after successfully storing it
        self.visited_urls.add(normalized_url)

        # Parse the HTML content
        soup = self._parse_html(response, normalized_url)
        if not soup:
            return None

        # Extract links from the parsed HTML
        raw_links = extract_links(soup, normalized_url)
        self._log_extracted_links(raw_links)

        # Limit the number of links if in test mode
        if self.test_mode:
            raw_links = self._limit_links_for_test_mode(raw_links)

        # Format links for analysis
        links_with_context = self._format_links(raw_links)
        logger.debug(f"Formatted links: {links_with_context}")

        # Filter out links that have already been analyzed
        new_links = self._filter_new_links(links_with_context)
        if not new_links:
            logger.info("No new links to analyze.")
            return None

        # Analyze the new links using Gemini
        analyzed_links = self._analyze_links(new_links, high_priority_keywords, medium_priority_keywords)
        if not analyzed_links:
            logger.info("No links analyzed as relevant.")
            return None

        try:
            # Store the analyzed links in the database
            formatted_links = self._format_links_for_db(analyzed_links)
            self.db.store_links(formatted_links, page_id)
            logger.info(f"Stored page {normalized_url} with ID {page_id} and {len(analyzed_links)} links.")
        except Exception as e:
            logger.error(f"Error processing links for page {normalized_url}: {e}")
            return None

        # Recursively crawl child links if depth allows
        if current_depth < self.max_depth:
            self._crawl_child_links(analyzed_links, high_priority_keywords, medium_priority_keywords, current_depth)

        return {"url": normalized_url, "num_links": len(analyzed_links), "links": analyzed_links}

    def _is_valid_depth(self, current_depth: int) -> bool:
        """Check if the current depth is within the allowed maximum depth."""
        if current_depth > self.max_depth:
            logger.debug(f"Reached max depth: {self.max_depth}")
            return False
        return True

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
        for link in raw_links:
            logger.debug(f"Extracted link: {link}")

    def _limit_links_for_test_mode(self, raw_links: List[Dict]) -> List[Dict]:
        """Limit the number of links processed in test mode."""
        if len(raw_links) > self.max_links:
            logger.info(f"🧪 Test mode: Limiting links from {len(raw_links)} to {self.max_links}.")
            return raw_links[: self.max_links]
        return raw_links

    def _format_links(self, raw_links: List[Dict]) -> List[Dict]:
        """Format raw links for analysis."""
        return [
            {
                "url": link.get("url"),
                "title": link.get("title", ""),
                "link_text": link.get("link_text", ""),
                "context": link.get("context", ""),
            }
            for link in raw_links
        ]

    def _filter_new_links(self, links_with_context: List[Dict]) -> List[Dict]:
        """Filter out links that have already been analyzed and stored."""
        new_links = []
        for link in links_with_context:
            if link["url"] and not self.db.link_exists(link["url"]):
                new_links.append(link)
            else:
                logger.debug(f"Skipping already analyzed link: {link['url']}")
        return new_links

    def _analyze_links(
        self, new_links: List[Dict], high_priority_keywords: List[str], medium_priority_keywords: List[str]
    ) -> List[Dict]:
        """Analyze new links using Gemini API."""
        logger.info(f"🤖 Analyzing {len(new_links)} new links with Gemini.")
        analyzed_links = analyze_page_content(
            new_links, high_priority_keywords, medium_priority_keywords, test_mode=self.test_mode
        )
        if analyzed_links:
            logger.info(f"✅ Successfully analyzed {len(analyzed_links)} relevant links.")
        else:
            logger.info("No links analyzed as relevant.")
        return analyzed_links

    def _format_links_for_db(self, analyzed_links: List[Dict]) -> List[Dict]:
        """Prepare analyzed links for database insertion."""
        formatted = []
        for link in analyzed_links:
            # Get the keyword lists and ensure they're lists of strings
            high_priority = link.get("high_priority_keywords", [])
            medium_priority = link.get("medium_priority_keywords", [])

            if isinstance(high_priority, str):
                high_priority = [high_priority]
            if isinstance(medium_priority, str):
                medium_priority = [medium_priority]

            # Ensure each keyword is a complete word, not individual characters
            high_priority = [
                "".join(kw) if isinstance(kw, (list, tuple)) else str(kw).strip() for kw in high_priority if kw
            ]
            medium_priority = [
                "".join(kw) if isinstance(kw, (list, tuple)) else str(kw).strip() for kw in medium_priority if kw
            ]

            # Convert to comma-separated strings
            high_priority_str = ", ".join(high_priority)
            medium_priority_str = ", ".join(medium_priority)

            formatted_link = {
                "url": link["url"],
                "title": link.get("title", ""),
                "relevancy": link.get("relevancy", 0.0),
                "relevancy_explanation": link.get("relevancy_explanation", ""),
                "high_priority_keywords": high_priority_str,
                "medium_priority_keywords": medium_priority_str,
                "context": link.get("context", ""),
            }

            formatted.append(formatted_link)
        return formatted

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
