import unittest
from unittest.mock import patch, MagicMock
import sqlite3
from src.web_crawler.database import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.db_path = ":memory:"  # Use in-memory SQLite for testing
        self.db = Database(self.db_path)

    def tearDown(self):
        """Clean up after each test method."""
        self.db.conn.close()

    def test_init_db(self):
        """Test database initialization."""
        # Verify tables exist
        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in self.db.cursor.fetchall()}
        self.assertIn("pages", tables)
        self.assertIn("links", tables)

    def test_init_db_failure(self):
        """Test database initialization failure."""
        with patch("sqlite3.connect") as mock_connect:
            mock_connect.side_effect = sqlite3.Error("Test error")
            with self.assertRaises(Exception):
                Database("invalid/path")

    def test_store_page(self):
        """Test storing a page in the database."""
        url = "https://example.com"
        page_id = self.db.store_page(url)

        self.db.cursor.execute("SELECT url FROM pages WHERE id = ?", (page_id,))
        result = self.db.cursor.fetchone()
        self.assertEqual(result[0], url)

    def test_store_duplicate_page(self):
        """Test storing a duplicate page."""
        url = "https://example.com"
        first_id = self.db.store_page(url)
        second_id = self.db.store_page(url)
        self.assertEqual(first_id, second_id)

    def test_store_links(self):
        """Test storing links in the database."""
        page_id = self.db.store_page("https://example.com")
        links = [
            {
                "url": "https://example.com/1",
                "title": "Test Title",
                "link_text": "Test Link",
                "relevancy": 0.8,
                "relevancy_explanation": "Test explanation",
                "high_priority_keywords": ["test"],
                "medium_priority_keywords": ["example"],
                "context": "Test context",
            }
        ]

        self.db.store_links(links, page_id)

        self.db.cursor.execute("SELECT url, title FROM links WHERE source_page_id = ?", (page_id,))
        result = self.db.cursor.fetchone()
        self.assertEqual(result[0], "https://example.com/1")
        self.assertEqual(result[1], "Test Title")

    def test_page_exists(self):
        """Test checking if page exists."""
        url = "https://example.com"
        self.db.store_page(url)
        self.assertTrue(self.db.page_exists(url))
        self.assertFalse(self.db.page_exists("https://nonexistent.com"))

    def test_link_exists(self):
        """Test checking if link exists."""
        page_id = self.db.store_page("https://example.com")
        link = {
            "url": "https://example.com/1",
            "title": "Test Title",
            "link_text": "Test Link",
            "relevancy": 0.8,
            "relevancy_explanation": "Test explanation",
            "high_priority_keywords": ["test"],
            "medium_priority_keywords": ["example"],
            "context": "Test context",
        }
        self.db.store_links([link], page_id)
        self.assertTrue(self.db.link_exists("https://example.com/1"))
        self.assertFalse(self.db.link_exists("https://nonexistent.com"))


if __name__ == "__main__":
    unittest.main()
