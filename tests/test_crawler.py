import unittest
from unittest.mock import patch, MagicMock
import requests
from src.web_crawler.crawler import Crawler
from src.web_crawler.database import Database
from src.web_crawler.utils import normalize_url
from requests.models import Response
from bs4 import BeautifulSoup


class TestCrawler(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_db = MagicMock(spec=Database)
        self.crawler = Crawler(self.mock_db, test_mode=True)

    def test_init(self):
        """Test crawler initialization."""
        self.assertTrue(self.crawler.test_mode)
        self.assertEqual(self.crawler.visited_urls, set())
        self.assertIsNotNone(self.crawler.session)

    def test_test_mode_configuration(self):
        """Test configuration is properly set for test mode."""
        self.crawler._set_mode_configuration()
        self.assertEqual(self.crawler.urls, self.crawler.urls)
        self.assertIsNotNone(self.crawler.max_links)
        self.assertIsNotNone(self.crawler.max_pages)
        self.assertIsNotNone(self.crawler.max_depth)
        self.assertIsNotNone(self.crawler.batch_size)

    @patch("requests.Session")
    def test_init_session(self, mock_session):
        """Test session initialization."""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        session = self.crawler._init_session()

        self.assertEqual(session, mock_session_instance)
        mock_session_instance.headers.update.assert_called_once()

    @patch("requests.Session")
    def test_production_mode(self, mock_session):
        """Test crawler in production mode."""
        crawler = Crawler(self.mock_db, test_mode=False)
        self.assertFalse(crawler.test_mode)
        self.assertNotEqual(crawler.max_pages, self.crawler.max_pages)

    @patch("src.web_crawler.crawler.requests.Session.get")
    def test_fetch_page_success(self, mock_get):
        """Test successful page fetch."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_get.return_value = mock_response

        url = "https://example.com"
        response = self.crawler._fetch_page(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "<html><body>Test content</body></html>")

    @patch("src.web_crawler.crawler.requests.Session.get")
    def test_fetch_page_failure(self, mock_get):
        """Test failed page fetch due to exception."""
        mock_get.side_effect = Exception("Connection error")

        url = "https://example.com"
        with self.assertRaises(Exception):
            self.crawler._fetch_page(url)

    @patch("src.web_crawler.crawler.requests.Session.get")
    def test_fetch_page_non_html_content(self, mock_get):
        """Test fetching a page with non-HTML content-type."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.text = "This is not HTML content."
        mock_response.headers = {"content-type": "application/json"}
        mock_get.return_value = mock_response

        url = "https://example.com/api/data"
        response = self.crawler._fetch_page(url)

        self.assertIsNone(response)

    @patch("src.web_crawler.crawler.requests.Session.get")
    def test_fetch_page_redirect(self, mock_get):
        """Test fetching a page that results in a redirect."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com/redirected"
        mock_response.history = [MagicMock(status_code=301)]
        mock_response.text = "<html><body>Redirected content</body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_get.return_value = mock_response

        url = "https://example.com"
        response = self.crawler._fetch_page(url)

        self.assertEqual(response.url, "https://example.com/redirected")
        self.assertEqual(len(response.history), 1)
        self.assertEqual(response.history[0].status_code, 301)

    def test_visited_urls_tracking(self):
        """Test tracking of visited URLs."""
        test_url = "https://example.com"
        self.assertNotIn(test_url, self.crawler.visited_urls)
        self.crawler.visited_urls.add(test_url)
        self.assertIn(test_url, self.crawler.visited_urls)

    def test_max_limits(self):
        """Test crawler respects maximum limits."""
        self.assertGreater(self.crawler.max_pages, 0)
        self.assertGreater(self.crawler.max_depth, 0)
        self.assertGreater(self.crawler.max_links, 0)
        self.assertGreater(self.crawler.batch_size, 0)

    def test_normalize_url_failure(self):
        """Test handling of invalid URLs during normalization."""
        invalid_url = "ht!tp://[invalid-url]"
        normalized = normalize_url(invalid_url)
        self.assertIsNone(normalized)

    @patch("src.web_crawler.crawler.normalize_url")
    def test_crawl_page_invalid_url(self, mock_normalize_url):
        """Test crawling a page with an invalid URL."""
        mock_normalize_url.return_value = None
        result = self.crawler.crawl_page("invalid-url", [], [], current_depth=0)
        self.assertIsNone(result)

    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawl_page_fetch_failure(self, mock_fetch_page):
        """Test crawling a page that fails to fetch."""
        mock_fetch_page.side_effect = Exception("Fetch failed after retries")
        result = self.crawler.crawl_page("https://example.com", [], [], current_depth=0)
        self.assertIsNone(result)

    @patch("src.web_crawler.crawler.Crawler._parse_html")
    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawl_page_parse_failure(self, mock_fetch_page, mock_parse_html):
        """Test crawling a page that fails to parse."""
        mock_response = MagicMock(spec=Response)
        mock_response.text = "<html></html>"
        mock_fetch_page.return_value = mock_response
        mock_parse_html.return_value = None

        result = self.crawler.crawl_page("https://example.com", [], [], current_depth=0)
        self.assertIsNone(result)

    @patch("src.web_crawler.crawler.Crawler._analyze_links")
    @patch("src.web_crawler.crawler.Crawler._parse_html")
    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawl_page_no_new_links(self, mock_fetch_page, mock_parse_html, mock_analyze_links):
        """Test crawling a page with no new links to analyze."""
        mock_response = MagicMock(spec=Response)
        mock_response.text = "<html><body>No links here</body></html>"
        mock_fetch_page.return_value = mock_response

        mock_soup = BeautifulSoup("<html><body>No links here</body></html>", "html.parser")
        mock_parse_html.return_value = mock_soup

        self.crawler.db.link_exists.return_value = True  # Simulate that all links already exist
        result = self.crawler.crawl_page("https://example.com", [], [], current_depth=0)
        self.assertEqual(result, {"url": "https://www.example.com", "num_links": 0, "links": []})
        mock_analyze_links.assert_not_called()

    @patch("src.web_crawler.crawler.analyze_page_content")
    @patch("src.web_crawler.crawler.Crawler._format_links")
    @patch("src.web_crawler.crawler.Crawler._filter_new_links")
    @patch("src.web_crawler.crawler.Crawler._parse_html")
    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawl_page_analyze_failure(
        self, mock_fetch_page, mock_parse_html, mock_filter_new_links, mock_format_links, mock_analyze_page_content
    ):
        """Test crawling a page where Gemini analysis fails."""
        mock_response = MagicMock(spec=Response)
        mock_response.text = "<html><body>Links here</body></html>"
        mock_fetch_page.return_value = mock_response

        mock_soup = BeautifulSoup("<html><body>Links here</body></html>", "html.parser")
        mock_parse_html.return_value = mock_soup

        mock_filter_new_links.return_value = [{"url": "https://example.com/link1"}]
        mock_format_links.return_value = [{"url": "https://example.com/link1"}]
        mock_analyze_page_content.return_value = None  # Simulate analysis failure

        result = self.crawler.crawl_page("https://example.com", [], [], current_depth=0)
        self.assertIsNone(result)

    @patch("src.web_crawler.crawler.Crawler._format_links_for_db")
    @patch("src.web_crawler.crawler.Crawler._analyze_links")
    @patch("src.web_crawler.crawler.Crawler._format_links")
    @patch("src.web_crawler.crawler.Crawler._filter_new_links")
    @patch("src.web_crawler.crawler.Crawler._parse_html")
    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawl_page_db_store_failure(
        self,
        mock_fetch_page,
        mock_parse_html,
        mock_filter_new_links,
        mock_format_links,
        mock_analyze_links,
        mock_format_links_for_db,
    ):
        """Test crawling a page where storing links in the database fails."""
        mock_response = MagicMock(spec=Response)
        mock_response.text = "<html><body>Links here</body></html>"
        mock_fetch_page.return_value = mock_response

        mock_soup = BeautifulSoup("<html><body>Links here</body></html>", "html.parser")
        mock_parse_html.return_value = mock_soup

        mock_filter_new_links.return_value = [{"url": "https://example.com/link1"}]
        mock_format_links.return_value = [{"url": "https://example.com/link1"}]
        mock_analyze_links.return_value = [{"url": "https://example.com/link1"}]
        mock_format_links_for_db.return_value = [{"url": "https://example.com/link1"}]

        self.crawler.db.store_links.side_effect = Exception("Database error")

        result = self.crawler.crawl_page("https://example.com", [], [], current_depth=0)
        self.assertIsNone(result)

    def test_crawler_reaches_max_depth(self):
        """Test that the crawler stops when the maximum depth is reached."""
        self.crawler.max_depth = 1
        with patch.object(self.crawler, "_fetch_page") as mock_fetch_page:
            with patch.object(self.crawler, "_parse_html") as mock_parse_html:
                with patch.object(self.crawler, "_filter_new_links") as mock_filter_new_links:
                    with patch.object(self.crawler, "_analyze_links") as mock_analyze_links:
                        with patch.object(self.crawler, "_crawl_child_links") as mock_crawl_child_links:
                            mock_fetch_page.return_value = MagicMock(spec=Response)
                            mock_parse_html.return_value = BeautifulSoup("<html></html>", "html.parser")
                            mock_filter_new_links.return_value = []
                            mock_analyze_links.return_value = []

                            self.crawler.crawl_page("https://example.com", [], [], current_depth=1)
                            mock_crawl_child_links.assert_not_called()

    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawler_reaches_max_pages(self, mock_fetch_page):
        """Test that the crawler stops when the maximum number of pages is reached."""
        self.crawler.max_pages = 1
        mock_fetch_page.return_value = None
        self.crawler.visited_urls = set(["https://example.com"])
        result = self.crawler.crawl_page("https://another-example.com", [], [], current_depth=0)
        self.assertIsNone(result)

    def test_crawler_skips_already_visited_url(self):
        """Test that the crawler skips URLs that have already been visited."""
        url = "https://example.com"
        normalized_url = normalize_url(url)
        self.crawler.visited_urls.add(normalized_url)
        with patch.object(self.crawler, "_fetch_page") as mock_fetch_page:
            result = self.crawler.crawl_page(url, [], [], current_depth=0)
            self.assertIsNone(result)
            mock_fetch_page.assert_not_called()

    @patch("src.web_crawler.crawler.Crawler._parse_html")
    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawler_handles_malformed_html(self, mock_fetch_page, mock_parse_html):
        """Test that the crawler handles pages with malformed HTML."""
        mock_response = MagicMock(spec=Response)
        mock_response.text = "<html><body><div>Unclosed tags"
        mock_fetch_page.return_value = mock_response

        mock_parse_html.return_value = BeautifulSoup(mock_response.text, "html.parser")

        with patch.object(self.crawler, "_filter_new_links") as mock_filter_new_links:
            with patch.object(self.crawler, "_analyze_links") as mock_analyze_links:
                mock_filter_new_links.return_value = []
                mock_analyze_links.return_value = []

                result = self.crawler.crawl_page("https://example.com", [], [], current_depth=0)
                self.assertIsNotNone(result)

    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawler_handles_empty_response(self, mock_fetch_page):
        """Test that the crawler handles empty HTTP responses."""
        mock_response = MagicMock(spec=Response)
        mock_response.text = ""
        mock_response.headers = {"content-type": "text/html"}
        mock_fetch_page.return_value = mock_response

        with patch.object(self.crawler, "_parse_html") as mock_parse_html:
            mock_parse_html.return_value = None
            result = self.crawler.crawl_page("https://example.com", [], [], current_depth=0)
            self.assertIsNone(result)

    def test_crawler_handles_none_url(self):
        """Test that the crawler gracefully handles None as a URL."""
        result = self.crawler.crawl_page(None, [], [], current_depth=0)
        self.assertIsNone(result)

    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawler_handles_invalid_url_format(self, mock_fetch_page):
        """Test that the crawler handles invalid URL formats."""
        invalid_url = "htp:/invalid-url"
        result = self.crawler.crawl_page(invalid_url, [], [], current_depth=0)
        self.assertIsNone(result)
        mock_fetch_page.assert_not_called()

    def test_crawler_max_links_limit(self):
        """Test that the crawler respects the max_links limit in test mode."""
        self.crawler.test_mode = True
        self.crawler.max_links = 2

        raw_links = [
            {"url": "https://example.com/link1"},
            {"url": "https://example.com/link2"},
            {"url": "https://example.com/link3"},
        ]

        limited_links = self.crawler._limit_links_for_test_mode(raw_links)
        self.assertEqual(len(limited_links), 2)

    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawler_handles_timeout(self, mock_fetch_page):
        """Test that the crawler handles request timeouts."""
        mock_fetch_page.side_effect = requests.exceptions.Timeout("Request timed out")
        with self.assertRaises(Exception):
            self.crawler._fetch_page("https://example.com")

    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawler_handles_ssl_error(self, mock_fetch_page):
        """Test that the crawler handles SSL errors."""
        mock_fetch_page.side_effect = requests.exceptions.SSLError("SSL Error")
        with self.assertRaises(Exception):
            self.crawler._fetch_page("https://example.com")

    @patch("src.web_crawler.crawler.Crawler._fetch_page")
    def test_crawler_handles_connection_error(self, mock_fetch_page):
        """Test that the crawler handles connection errors."""
        mock_fetch_page.side_effect = requests.exceptions.ConnectionError("Connection Error")
        with self.assertRaises(Exception):
            self.crawler._fetch_page("https://example.com")


if __name__ == "__main__":
    unittest.main()
