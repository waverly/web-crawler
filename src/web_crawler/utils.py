import functools
import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            return None
        # Additional validation can be added here
        normalized_netloc = parsed.netloc.lower()
        if not normalized_netloc.startswith("www."):
            normalized_netloc = "www." + normalized_netloc
        normalized_url = urlunparse(
            (parsed.scheme.lower(), normalized_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
        )
        return normalized_url
    except Exception as e:
        logger.error(f"Error normalizing URL {url}: {e}")
        return None


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


def exponential_backoff(
    max_retries: int = 3,
    exceptions: Tuple[Exception, ...] = (Exception,),
    base_delay: float = 1.0,
) -> Callable:
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
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds...")
                    time.sleep(delay)
            # This line should not be reached
            return None

        return wrapper

    return decorator


def parse_url(url: str) -> Tuple[str, str]:
    """Parse URL into domain and path."""
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path or "/"
    return domain, path


def extract_links(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """Extract links from BeautifulSoup object with improved context extraction."""
    logger.debug(f"Starting link extraction from {base_url}")

    links = []
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

    # Skip patterns for URLs
    skip_patterns = [
        r"^javascript:",  # JavaScript links
        r"^#",  # Anchor links
        r"void\(0\)",  # JavaScript void
        r"^$",  # Empty links
    ]
    skip_regex = re.compile("|".join(skip_patterns))

    # Find all anchor tags
    all_anchors = soup.find_all("a", href=True)
    # logger.debug(f"Found {len(all_anchors)} anchor tags")

    for a_tag in all_anchors:
        href = a_tag["href"]
        logger.debug(f"\nProcessing link with href: {href}")

        # Skip unwanted link types
        if skip_regex.search(href):
            # logger.debug(f"Skipping link with pattern match: {href}")
            continue

        # More strict image check
        if a_tag.find("img"):
            img = a_tag.find("img")
            src = img.get("src", "").lower()
            if "spacer.gif" in src:
                logger.debug(f"Skipping spacer image link: {a_tag}")
                continue
            if href.lower().endswith(".pdf"):
                logger.debug("Keeping PDF link with image")
            else:
                logger.debug(f"Skipping image link: {a_tag}")
                continue

        # Skip links that are just fragments of the current URL
        if href.startswith("#sitebody"):
            logger.debug("Skipping sitebody fragment")
            continue

        # if href.startswith("mailto:"):
        #     logger.debug("Found mailto link - preserving for contact information")
        #     email = href.replace("mailto:", "")
        #     links.append(
        #         {
        #             "url": href,
        #             "link_text": email,
        #             "context": f"Contact email address: {email}",
        #             "is_contact": True,  # Add flag for contact info
        #         }
        #     )
        #     continue

        # if href.startswith("tel:"):
        #     logger.debug("Found tel link - preserving for contact information")
        #     phone_number = href.replace("tel:", "")
        #     links.append(
        #         {
        #             "url": href,
        #             "link_text": phone_number,
        #             "context": f"Contact phone number: {phone_number}",
        #             "is_contact": True,  # Add flag for contact info
        #         }
        #     )
        #     continue

        absolute_url = requests.compat.urljoin(base_url, href)

        # Skip if the absolute URL matches any skip patterns
        if skip_regex.search(absolute_url):
            logger.debug(f"Skipping absolute URL with pattern match: {absolute_url}")
            continue

        # logger.debug(f"Absolute URL: {absolute_url}")

        # Get link text with detailed logging
        link_text = a_tag.get_text(strip=True)
        # logger.debug(f"Raw anchor tag: {a_tag}")
        # logger.debug(f"Extracted link text: {link_text}")

        # Skip empty links
        if not link_text:
            logger.debug("Skipping empty link text")
            continue

        try:
            # Find the closest block-level parent
            block_parent = a_tag.find_parent(block_elements)
            if block_parent:
                context = block_parent.get_text(" ", strip=True)
                # logger.debug(f"Found block parent: {block_parent.name}")
            else:
                # logger.debug("No block parent found, getting surrounding text")
                previous_text = a_tag.find_previous(string=True)
                next_text = a_tag.find_next(string=True)
                context = " ".join(filter(None, [previous_text, link_text, next_text]))
                # logger.debug(f"Previous text: {previous_text}")
                # logger.debug(f"Next text: {next_text}")

            # Fallback: use page title or URL
            if not context.strip():
                page_title = soup.title.string if soup.title else ""
                context = f"From page: {page_title or absolute_url}"
                # logger.debug("Using fallback context")

            # Clean up the context
            context = re.sub(r"\s+", " ", context).strip()
            if len(context) > 500:
                context = context[:497] + "..."

            links.append(
                {
                    "url": absolute_url,
                    "link_text": link_text,
                    "context": context,
                }
            )
            logger.debug(f"Successfully added link with text: {link_text}")

        except Exception as e:
            logger.error(f"Error processing link {href}: {str(e)}")
            continue

    return links


def parse_keywords(keywords_str: str) -> List[str]:
    """Parse comma-separated keywords from CLI prompt into a list."""
    if not keywords_str:
        return []
    return [k.strip() for k in keywords_str.split(",") if k.strip()]


def extract_json(text: str) -> List[Dict]:
    """Extract JSON from text, handling markdown code blocks."""
    if not text.strip():
        logger.error("Received empty text to parse")
        return []

    # Remove markdown code block markers if present
    cleaned_text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()

    try:
        parsed_json = json.loads(cleaned_text)
        if isinstance(parsed_json, list):
            return parsed_json
        else:
            logger.error("Parsed JSON is not a list.")
            return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        logger.error(f"Failed text: {cleaned_text}")
        return []
