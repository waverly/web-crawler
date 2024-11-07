from fastapi import FastAPI, HTTPException, Query
from typing import Optional, List

from src.web_crawler.types import LinkResponse
from . import database
from . import config
import json
import os
import sqlite3
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Web Crawler API",
    description="""
    API for accessing crawled web pages and their links.
    
    ## Features
    * List crawled pages with pagination and domain filtering
    * Get links discovered on specific pages
    * Search pages by keyword
    
    ## Usage
    All endpoints return JSON responses and support query parameters for filtering.
    """,
    version="1.0.0",
)

# Debug the path resolution
current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)
DB_PATH = "/Users/waverly/Documents/webcrawler-demo/" + config.DATABASE_PATH  # Exact path from your pwd command

# Also verify the file exists
print(f"Database file exists: {os.path.exists(DB_PATH)}")
print(f"Database file size: {os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 'N/A'}")

# Let's also try to read it directly
try:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pages")
        count = cursor.fetchone()[0]
        print(f"Direct SQLite count: {count}")
except Exception as e:
    print(f"Error reading database: {e}")

# Initialize database with absolute path
db = database.Database(db_path=DB_PATH)


class PrettyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=False, allow_nan=False, indent=2, separators=(", ", ": ")).encode(
            "utf-8"
        )


@app.get("/", tags=["General"])
async def root():
    """
    Welcome endpoint with basic API information.
    """
    return {"message": "Welcome to the Web Crawler API. Visit /docs for documentation."}


@app.get("/pages", response_class=PrettyJSONResponse)
def get_pages():
    """Get all crawled pages with their link counts."""
    with db.get_api_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT p.id, p.url,
                    COUNT(l.id) as link_count,
                    SUM(CASE WHEN l.relevancy >= 0.7 THEN 1 ELSE 0 END) as high_priority_count,
                    SUM(CASE WHEN l.relevancy >= 0.3 AND l.relevancy < 0.7 THEN 1 ELSE 0 END) as medium_priority_count
                FROM pages p
                LEFT JOIN links l ON l.source_page_id = p.id
                GROUP BY p.id, p.url
                ORDER BY p.id DESC
                """
            )

            pages = []
            for row in cursor.fetchall():
                pages.append(
                    {
                        "id": row[0],
                        "url": row[1],
                        "total_links": row[2],
                        "high_priority_links": row[3],
                        "medium_priority_links": row[4],
                    }
                )

            return {"pages": pages}
        except Exception as e:
            print(f"Error reading database: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/pages/{page_id}/links", response_model=List[LinkResponse], tags=["Links"])
def get_page_links(
    page_id: int, min_priority: float = Query(0.0, ge=0.0, le=1.0, description="Minimum priority threshold")
):
    """Get links found on a specific page."""
    with db.get_api_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM links 
            WHERE source_page_id = ? AND relevancy >= ?
            ORDER BY relevancy DESC
            """,
            (page_id, min_priority),
        )
        link_ids = [row[0] for row in cursor.fetchall()]

        # Use get_link to fetch each link with properly formatted keywords
        results = []
        for link_id in link_ids:
            link = db.get_link(link_id)
            if link:
                results.append(link)
        return results


@app.get("/search", response_class=PrettyJSONResponse)
def search_links(query: str, min_priority: Optional[float] = None, limit: int = 100):
    """Search for links containing the query string."""
    with db.get_api_connection() as conn:
        cursor = conn.cursor()

        sql = """
            SELECT 
                l.id,
                l.source_page_id,
                p.url as source_url,
                l.url,
                l.title,
                l.relevancy,
                l.relevancy_explanation,
                l.high_priority_keywords,
                l.medium_priority_keywords,
                l.context
            FROM links l
            JOIN pages p ON p.id = l.source_page_id
            WHERE (
                l.url LIKE ? OR 
                l.title LIKE ? OR 
                l.high_priority_keywords LIKE ? OR 
                l.medium_priority_keywords LIKE ? OR 
                l.context LIKE ?
            )
        """

        if min_priority is not None:
            sql += " AND l.relevancy >= ?"

        sql += " ORDER BY l.relevancy DESC"
        sql += " LIMIT ?"

        pattern = f"%{query}%"
        params = [pattern] * 5

        if min_priority is not None:
            params.append(min_priority)

        params.append(limit)

        cursor.execute(sql, params)

        links = []
        for row in cursor.fetchall():
            links.append(
                {
                    "id": row[0],
                    "source_page_id": row[1],
                    "source_url": row[2],
                    "url": row[3],
                    "title": row[4],
                    "relevancy": row[5],
                    "relevancy_explanation": row[6],
                    "high_priority_keywords": row[7] if row[7] else [],
                    "medium_priority_keywords": row[8] if row[8] else [],
                    "context": row[9],
                }
            )

        return {"query": query, "min_priority": min_priority, "count": len(links), "links": links}


def format_link(row) -> dict:
    """Format a link row into a nice dictionary."""
    # Parse keywords properly - they should be comma-separated strings
    high_priority = row[7].split(",") if row[7] else []
    medium_priority = row[8].split(",") if row[8] else []

    # Strip whitespace and filter empty strings
    high_priority = [k.strip() for k in high_priority if k.strip()]
    medium_priority = [k.strip() for k in medium_priority if k.strip()]

    return {
        "id": row[0],
        "source": {"id": row[1], "url": row[2]},
        "url": row[3],
        "title": row[4] or "(no title)",
        "relevancy": float(row[5]),
        "relevancy_explanation": row[6],
        "keywords": {"high_priority": high_priority, "medium_priority": medium_priority},
        "context": row[9] if row[9] else "(no context)",
    }


# create a new connection for each request
def get_db_connection():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), config.DATABASE_PATH)
    return sqlite3.connect(db_path)


@app.get("/links", response_class=PrettyJSONResponse)
def get_links(
    page: int = Query(1, description="Page number", ge=1),
    per_page: int = Query(10, description="Items per page", ge=1, le=100),
    min_relevancy: float = Query(0.0, description="Minimum relevancy score", ge=0.0, le=1.0),
):
    """Get all links with pagination and filtering."""
    with db.get_api_connection() as conn:
        cursor = conn.cursor()
        try:
            # First get total count
            count_query = """
                SELECT COUNT(*) 
                FROM links l
                JOIN pages p ON p.id = l.source_page_id
                WHERE l.relevancy >= ?
            """
            cursor.execute(count_query, [min_relevancy])
            total_count = cursor.fetchone()[0]

            # Then get paginated link IDs
            query = """
                SELECT l.id
                FROM links l
                JOIN pages p ON p.id = l.source_page_id
                WHERE l.relevancy >= ?
                ORDER BY l.relevancy DESC
                LIMIT ? OFFSET ?
            """

            offset = (page - 1) * per_page
            cursor.execute(query, [min_relevancy, per_page, offset])
            link_ids = [row[0] for row in cursor.fetchall()]

            # Use get_link to fetch each link with properly formatted keywords
            links = []
            for link_id in link_ids:
                link = db.get_link(link_id)
                if link:
                    links.append(link)

            return {
                "links": links,
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "pages": (total_count + per_page - 1) // per_page,
            }
        except Exception as e:
            print(f"Database connection error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
