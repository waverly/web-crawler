"""Database operations for the web crawler."""

import sqlite3
import logging
from typing import List, Optional, Dict
from contextlib import contextmanager
import json
from .types import Link

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        """Initialize database connection."""
        try:
            self.db_path = db_path
            self.conn = sqlite3.connect(db_path)
            self.cursor = self.conn.cursor()
            self._init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

    def _init_db(self):
        """Initialize the database tables and indexes."""
        try:
            # Create tables
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_page_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
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
            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_links_source_page 
                ON links(source_page_id)
            """
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}")
            raise

    def clear(self):
        """Clear all data from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM links")
            cursor.execute("DELETE FROM pages")
            conn.commit()
            logger.info("Database cleared!")

    def store_page(self, url: str) -> Optional[int]:
        """
        Store a page in the database and return its ID.
        If the page already exists, return the existing ID.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO pages (url) VALUES (?)
            """,
                (url,),
            )
            conn.commit()

            cursor.execute("SELECT id FROM pages WHERE url = ?", (url,))
            result = cursor.fetchone()
            if result:
                page_id = result[0]
                logger.info(f"Page ID {page_id} for URL: {url}")
                return page_id
            else:
                logger.error(f"Failed to store or retrieve page ID for URL: {url}")
                return None

    def link_exists(self, url: str) -> bool:
        """Check if a link has already been analyzed and stored."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT 1 FROM links WHERE url = ?", (url,))
            return cursor.fetchone() is not None

    def store_links(self, links: List[Link], page_id: int) -> None:
        """Store links in database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for link in links:
                    # Convert lists to strings with space after comma
                    high_priority_str = ", ".join(
                        str(kw).strip() for kw in link.get("high_priority_keywords", []) if kw
                    )
                    medium_priority_str = ", ".join(
                        str(kw).strip() for kw in link.get("medium_priority_keywords", []) if kw
                    )

                    cursor.execute(
                        """
                        INSERT INTO links (
                            source_page_id, url, title, link_text, relevancy, 
                            relevancy_explanation,
                            high_priority_keywords, medium_priority_keywords, context
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            page_id,
                            link["url"],
                            link.get("title", ""),
                            link.get("link_text", ""),
                            link.get("relevancy", 0.0),
                            link.get("relevancy_explanation", ""),
                            high_priority_str,
                            medium_priority_str,
                            link.get("context", ""),
                        ),
                    )
                conn.commit()
                logger.info(f"Successfully stored {len(links)} links")
        except Exception as e:
            logger.error(f"Error storing links: {str(e)}")
            logger.error(f"Failed links data: {json.dumps(links, indent=2)}")
            raise

    def _convert_keywords_to_list(self, keywords_str: str) -> List[str]:
        """Convert a comma-separated string of keywords to a list."""
        if not keywords_str:
            return []

        # Split on commas and filter out empty strings
        keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]

        # If we got a single word that was split into characters, join it back
        if len(keywords) > 1 and all(len(k) == 1 for k in keywords):
            return ["".join(keywords)]

        return keywords

    def get_link(self, link_id: int) -> Optional[Dict]:
        """Get a link by ID with properly formatted keywords."""
        with self.get_api_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, url, title, link_text, relevancy, 
                       relevancy_explanation, high_priority_keywords,
                       medium_priority_keywords, context
                FROM links WHERE id = ?
            """,
                (link_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            # Convert the row to a dict with proper keyword lists
            link = {
                "id": row[0],
                "url": row[1],
                "title": row[2],
                "link_text": row[3],
                "relevancy": row[4],
                "relevancy_explanation": row[5],
                "high_priority_keywords": self._convert_keywords_to_list(row[6]),
                "medium_priority_keywords": self._convert_keywords_to_list(row[7]),
                "context": row[8],
            }
            return link

    def page_exists(self, url: str) -> bool:
        """Check if a page with the given URL exists in the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM pages WHERE url = ?", (url,))
            return cursor.fetchone() is not None

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        try:
            yield self.conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursors."""
        try:
            yield self.cursor
            self.conn.commit()
        except Exception as e:
            logger.error(f"Database cursor error: {e}")
            raise

    def __del__(self):
        """Close database connection on object destruction."""
        if hasattr(self, "conn") and self.conn:
            try:
                self.conn.close()
                logger.debug("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")

    @contextmanager
    def get_api_connection(self):
        """Context manager for thread-safe API database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            logger.error(f"API database connection error: {e}")
            raise
        finally:
            conn.close()
