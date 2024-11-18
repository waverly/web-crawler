"""Database operations for the web crawler.
    Operating under the assumption that this web crawler will handle
    multiple threads and manage connections appropriately.
"""

import sqlite3
import logging
from typing import List, Optional, Dict, Set
import json
import contextlib

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        """Initialize the database path."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database tables and indexes."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Create tables
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL UNIQUE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # Create index on pages.url
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_page_id INTEGER NOT NULL,
                        url TEXT NOT NULL,
                        link_text TEXT,
                        relevancy REAL,
                        relevancy_explanation TEXT,
                        high_priority_keywords TEXT,
                        medium_priority_keywords TEXT,
                        context TEXT,
                        FOREIGN KEY (source_page_id) REFERENCES pages(id)
                    )
                    """
                )

                # Create indexes
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_links_source_page 
                    ON links(source_page_id);
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_links_url ON links(url);
                    """
                )

                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

    @contextlib.contextmanager
    def get_connection(self):
        """Provide a transactional scope around a series of operations."""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,  # Allow connection to be used in different threads
        )
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {str(e)}")
            raise
        finally:
            conn.close()

    def store_page(self, url: str) -> int:
        """Store a page and return its ID."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO pages (url) VALUES (?)",
                    (url,),
                )
                conn.commit()
                cursor.execute("SELECT id FROM pages WHERE url = ?", (url,))
                page_id = cursor.fetchone()[0]
                return page_id
        except Exception as e:
            logger.error(f"Error storing page: {str(e)}")
            raise

    def store_links(self, links: List[Dict], page_id: int):
        """Store multiple links associated with a page."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for link in links:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO links (
                            source_page_id, url, link_text, relevancy, 
                            relevancy_explanation, high_priority_keywords, 
                            medium_priority_keywords, context
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            page_id,
                            link["url"],
                            link.get("link_text", ""),
                            link.get("relevancy", 0.0),
                            link.get("relevancy_explanation", ""),
                            ",".join(link.get("high_priority_keywords", [])),
                            ",".join(link.get("medium_priority_keywords", [])),
                            link.get("context", ""),
                        ),
                    )
                conn.commit()
                logger.info(f"Successfully stored {len(links)} links")
        except Exception as e:
            logger.error(f"Error storing links: {str(e)}")
            raise

    def page_exists(self, url: str) -> bool:
        """Check if a page with the given URL exists in the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM pages WHERE url = ?", (url,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking if page exists: {str(e)}")
            raise

    def link_exists(self, url: str) -> bool:
        """Check if a link has already been analyzed and stored."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM links WHERE url = ?", (url,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking if link exists: {str(e)}")
            raise

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

        # Use '?' placeholders for SQLite
        placeholders = ", ".join(["?"] * len(urls))
        query = f"SELECT url FROM pages WHERE url IN ({placeholders})"

        existing_urls = set()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, urls)
                results = cursor.fetchall()
                existing_urls = set(row[0] for row in results)
        except sqlite3.Error as e:
            logger.error(f"Database query failed: {e}")
            raise

        return existing_urls

    def get_mailto_and_tel_links(self) -> List[Dict]:
        """Retrieve all links that start with 'mailto:' or 'tel:'."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, source_page_id, url, link_text, relevancy, relevancy_explanation,
                           high_priority_keywords, medium_priority_keywords, context
                    FROM links
                    WHERE url LIKE 'mailto:%' OR url LIKE 'tel:%';
                    """
                )
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                links = [dict(zip(columns, row)) for row in rows]
                logger.info(f"Retrieved {len(links)} 'mailto:' or 'tel:' links from the database.")
                return links
        except Exception as e:
            logger.error(f"Error retrieving mailto/tel links: {str(e)}")
            raise

    def __del__(self):
        """Cleanup is handled by context managers; nothing needed here."""
        pass
