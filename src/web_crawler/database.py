"""Database operations for the web crawler.
    Operating under the assumption that this web crawler will be single-threaded
    and thus will not need a unique connection per thread.
"""

import sqlite3
import logging
from typing import List, Optional, Dict
import json

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
            self.conn.rollback()
            logger.error(f"Error creating tables: {str(e)}")
            raise

    def clear(self):
        """Clear all data from the database."""
        try:
            self.cursor.execute("DELETE FROM links")
            self.cursor.execute("DELETE FROM pages")
            self.conn.commit()
            logger.info("Database cleared!")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error clearing database: {str(e)}")
            raise

    def store_page(self, url: str) -> Optional[int]:
        """
        Store a page in the database and return its ID.
        If the page already exists, return the existing ID.
        """
        try:
            self.cursor.execute(
                """
                INSERT OR IGNORE INTO pages (url) VALUES (?)
            """,
                (url,),
            )
            self.conn.commit()

            self.cursor.execute("SELECT id FROM pages WHERE url = ?", (url,))
            result = self.cursor.fetchone()
            if result:
                page_id = result[0]
                logger.info(f"Page ID {page_id} for URL: {url}")
                return page_id
            else:
                logger.error(f"Failed to store or retrieve page ID for URL: {url}")
                return None
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error storing page: {str(e)}")
            raise

    def store_links(self, links: List[Dict], page_id: int) -> None:
        """Store links in the database."""
        try:
            for link in links:
                # Convert lists to strings with commas
                high_priority_str = ", ".join(str(kw).strip() for kw in link.get("high_priority_keywords", []) if kw)
                medium_priority_str = ", ".join(
                    str(kw).strip() for kw in link.get("medium_priority_keywords", []) if kw
                )

                self.cursor.execute(
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
            self.conn.commit()
            logger.info(f"Successfully stored {len(links)} links")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error storing links: {str(e)}")
            logger.error(f"Failed links data: {json.dumps(links, indent=2)}")
            raise

    def page_exists(self, url: str) -> bool:
        """Check if a page with the given URL exists in the database."""
        try:
            self.cursor.execute("SELECT id FROM pages WHERE url = ?", (url,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking if page exists: {str(e)}")
            raise

    def link_exists(self, url: str) -> bool:
        """Check if a link has already been analyzed and stored."""
        try:
            self.cursor.execute("SELECT 1 FROM links WHERE url = ?", (url,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking if link exists: {str(e)}")
            raise

    def __del__(self):
        """Close database connection on object destruction."""
        if hasattr(self, "conn") and self.conn:
            try:
                self.conn.close()
                logger.debug("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
