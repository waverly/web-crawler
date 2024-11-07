import json
from urllib.parse import urlparse
import functools
import re
import time
from bs4 import BeautifulSoup
import requests
import logging
from typing import Callable, Any, Dict, List

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize URL to ensure www prefix if not present.
    Returns the normalized URL as a string.
    """
    try:
        # Parse the URL
        parsed = urlparse(url)
        domain = parsed.netloc

        # Add www if not present
        if not domain.startswith("www."):
            domain = "www." + domain

        # Reconstruct URL
        normalized = f"{parsed.scheme}://{domain}{parsed.path}"

        if parsed.query:
            normalized += f"?{parsed.query}"

        return normalized

    except Exception as e:
        logger.error(f"Error normalizing URL {url}: {str(e)}")
        # Return the original URL as fallback
        return url


# i would want to unit test this
def extract_domain(url: str) -> str:
    """Extract the domain from a URL.

    Args:
        url (str): The URL to process

    Returns:
        str: The extracted domain name

    Examples:
        >>> extract_domain('https://www.example.com/path')
        'example.com'
        >>> extract_domain('http://subdomain.example.co.uk/path')
        'example.co.uk'
    """
    # Parse the URL
    parsed = urlparse(url)
    # Get the netloc (network location) part
    domain = parsed.netloc

    # Remove www. if present
    if domain.startswith("www."):
        domain = domain[4:]

    # Handle special cases for country-specific domains (e.g., co.uk)
    parts = domain.split(".")
    if len(parts) > 2 and parts[-2] in ["co", "gov", "edu", "org"]:
        return ".".join(parts[-3:])

    # Return the main domain (last two parts)
    return ".".join(parts[-2:])


def exponential_backoff(max_retries: int = 3, exceptions: tuple = (Exception,), base_delay: float = 1.0) -> Callable:
    """Decorator for exponential backoff retry logic."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2**attempt)
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. " f"Retrying in {delay} seconds...")
                    time.sleep(delay)
            return None

        return wrapper

    return decorator


def parse_url(url: str) -> tuple[str, str]:
    """Parse URL into domain and path."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path or "/"
        return domain, path
    except Exception as e:
        logger.error(f"Error parsing URL {url}: {e}")
        # Return a default value if parsing fails
        return urlparse(url).netloc, "/"


# further optimization: could add more metadata, like is_external, is_pdf, etc.
# to classify and improve prioritization
def extract_links(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """Extract links from BeautifulSoup object with improved context extraction."""
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        try:
            absolute_url = requests.compat.urljoin(base_url, href)
            link_text = a_tag.get_text(strip=True)
            context = ""

            # Define block-level elements
            block_elements = [
                "p",
                "div",
                "section",
                "article",
                "li",
                "td",
                "th",
                "blockquote",
                "pre",
                "ul",
                "ol",
                "header",
                "footer",
                "nav",
            ]

            # Find the closest block-level parent
            block_parent = a_tag.find_parent(block_elements)
            if block_parent:
                context = block_parent.get_text(" ", strip=True)
            else:
                # If no block-level parent, get surrounding text nodes
                previous_text = a_tag.find_previous(string=True)
                next_text = a_tag.find_next(string=True)
                context = " ".join(filter(None, [previous_text, link_text, next_text]))

            # Fallback: use page title or URL
            if not context.strip():
                page_title = soup.title.string if soup.title else ""
                context = f"From page: {page_title or absolute_url}"

            # Clean up the context
            context = re.sub(r"\s+", " ", context).strip()
            if len(context) > 500:
                context = context[:497] + "..."

            links.append(
                {
                    "url": absolute_url,
                    "title": a_tag.get("title", ""),
                    "link_text": link_text,
                    "context": context,
                }
            )

        except Exception as e:
            # Even on error, provide minimal context
            links.append(
                {
                    "url": absolute_url,
                    "title": "",
                    "link_text": href,
                    "context": f"Found in {base_url}",
                }
            )
            continue

    return links


def parse_keywords(keywords_str: str) -> List[str]:
    """Parse comma-separated keywords from cli prompt into a list."""
    if not keywords_str:
        return []
    return [k.strip() for k in keywords_str.split(",") if k.strip()]


def extract_json(text: str) -> Dict:
    """Extract JSON from text, handling markdown code blocks."""
    if not text.strip():
        logger.error("Received empty text to parse")
        return {"links": []}

    # Remove markdown code block markers if present
    cleaned_text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        logger.error(f"Failed text: {cleaned_text}")
        return {"links": []}
