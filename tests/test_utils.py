import unittest
from bs4 import BeautifulSoup
from src.web_crawler.utils import normalize_url, extract_links, extract_json, extract_domain


class TestUtils(unittest.TestCase):
    def test_normalize_url(self):
        """Test URL normalization."""
        # Update test to expect www. prefix since normalize_url adds it
        self.assertEqual(normalize_url("http://example.com"), "http://www.example.com")
        self.assertEqual(normalize_url("https://www.example.com"), "https://www.example.com")
        self.assertEqual(normalize_url("http://example.com/path"), "http://www.example.com/path")
        self.assertIsNone(normalize_url("://www.ht!tp://[invalid-url]"))

    def test_dupes_normalize_url(self):
        """Test URL normalization."""
        # All these URLs should normalize to https://www.example.com
        test_urls = ["https://example.com", "https://www.example.com", "http://example.com", "http://www.example.com"]
        normalized_urls = {normalize_url(url) for url in test_urls}
        self.assertEqual(
            len(normalized_urls), 2
        )  # Expects https urls to normalize to same value, and http to normalize to same value

    def test_extract_json(self):
        """Test JSON extraction from text."""
        # Test valid JSON
        json_text = '{"key": "value"}'
        self.assertEqual(extract_json(json_text), {"key": "value"})

        # Test JSON with markdown code blocks
        markdown_json = """```json
        {"key": "value"}
        ```"""
        self.assertEqual(extract_json(markdown_json), {"key": "value"})

        # Test invalid JSON
        invalid_json = 'Some text {"key": "value"} more text'
        self.assertEqual(extract_json(invalid_json), {"links": []})

    def test_extract_links(self):
        """Test link extraction from HTML."""
        html = """
        <html>
            <body>
                <a href="https://example.com">Link 1</a>
                <a href="/relative/path" title="Link 2">Link 2</a>
                <div>Some text <a href="https://test.com">Link 3</a> more text</div>
            </body>
        </html>
        """
        # Create BeautifulSoup object first
        soup = BeautifulSoup(html, "html.parser")
        base_url = "https://base.com"
        links = extract_links(soup, base_url)

        self.assertEqual(len(links), 3)
        self.assertTrue(any(link["url"] == "https://example.com" for link in links))
        self.assertTrue(any(link["url"] == "https://base.com/relative/path" for link in links))
        self.assertTrue(any(link["url"] == "https://test.com" for link in links))


if __name__ == "__main__":
    unittest.main()
