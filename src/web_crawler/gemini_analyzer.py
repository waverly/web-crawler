"""
Content analyzer using Google's Gemini API.
Extracts and rates relevant links based on configurable keywords.
"""

import logging
from typing import Dict, List
import google.generativeai as genai

from .utils import extract_json
from .rate_limiter import RateLimiter
from . import config

logger = logging.getLogger(__name__)

# Initialize rate limiter once
rate_limiter = RateLimiter(calls_per_minute=15)  # Gemini's free tier limit

# Initialize model globally to reuse across calls, avoiding re-initialization
gemini_model = None


def init_gemini():
    """Initialize Gemini API client if not already initialized."""
    global gemini_model
    if not gemini_model:
        genai.configure(api_key=config.GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    return gemini_model


def analyze_page_content(
    links: List[Dict], high_priority_keywords: List[str], medium_priority_keywords: List[str], test_mode: bool = False
) -> List[Dict]:
    """Analyze links in batches to avoid rate limits."""

    model = init_gemini()

    if test_mode:
        logger.info(f"🧪 Test mode: limiting from {len(links)} to {config.TEST_MAX_LINKS} links")
        links = links[: config.TEST_MAX_LINKS]

    BATCH_SIZE = 5
    results = []

    total_batches = (len(links) + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(f"Will process {len(links)} links in {total_batches} batches")

    for i in range(0, len(links), BATCH_SIZE):
        batch_num = (i // BATCH_SIZE) + 1
        logger.info(f"📊 Processing batch {batch_num} of {total_batches}")

        batch = links[i : i + BATCH_SIZE]
        try:
            prompt = _create_prompt(batch, high_priority_keywords, medium_priority_keywords)
            rate_limiter.wait()
            response = model.generate_content(prompt)

            if not response or not response.text:
                logger.warning(f"Empty response for batch {batch_num}")
                continue

            try:
                parsed = extract_json(response.text)
                if parsed and isinstance(parsed, dict) and "links" in parsed:
                    batch_results = parsed["links"]
                    if isinstance(batch_results, list):
                        # Add debug logging
                        logger.info(
                            f"Gemini response for first link: {batch_results[0] if batch_results else 'No results'}"
                        )

                        # Preserve original context for each link
                        for i, result in enumerate(batch_results):
                            result["context"] = batch[i].get("context", "")
                        results.extend(batch_results)
                        logger.info(f"✅ Added {len(batch_results)} links from batch {batch_num}")
                else:
                    logger.warning(f"Invalid response structure in batch {batch_num}")
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {str(e)}")
                continue

        except Exception as e:
            logger.error(f"Error in batch {batch_num}: {str(e)}")
            continue

    if not results:
        logger.warning("No valid results found in any batch")
        return []

    logger.info(f"Successfully processed {len(results)} total links")
    return results


def _create_prompt(
    links_data: List[Dict], high_priority_keywords: List[str], medium_priority_keywords: List[str]
) -> str:
    links_text = ""
    for idx, link in enumerate(links_data):
        title = link.get("title", "")[:100].replace('"', '\\"')
        link_text = link.get("link_text", "")[:100].replace('"', '\\"')
        context = link.get("context", "")[:200].replace('"', '\\"')
        display_title = title if title else link_text
        links_text += f"""Link {idx+1}: URL={link['url']} Title="{display_title}" Context="{context}"\n"""

    return f"""You are an analyst identifying high-priority links from a webpage to assist in finding relevant government financial information.
                Output only JSON. Analyze these links for government financial information:

                Links: {links_text}

                High Priority: {', '.join(high_priority_keywords)}
                Medium Priority: {', '.join(medium_priority_keywords)}

                - Assess each link based on its title, URL, and surrounding context.
                - Determine a relevancy score that best represents the link's importance to government financial information.
                - Provide a brief explanation (1-2 sentences) for each relevancy score.
                - You may use a scoring system between 0.0 and 1.0
                - Preserve the original context in the output

                Output this exact JSON structure with no other text:
                {{
                "links": [
                    {{
                    "url": "string",
                    "title": "string",
                    "relevancy": number,
                    "relevancy_explanation": "string",
                    "high_priority_keywords": [],
                    "medium_priority_keywords": [],
                    "context": "string"
                    }}
                ]
                }}"""
