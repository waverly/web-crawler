"""
Content analyzer using OpenAI API.
Extracts and rates relevant links based on configurable keywords.
"""

import json
import logging
from typing import Dict, List
from openai import OpenAI

from .utils import extract_json
from . import config

logger = logging.getLogger(__name__)


# Initialize client globally to reuse across calls
openai_client = None


def init_openai():
    """Initialize OpenAI API client if not already initialized."""
    global openai_client
    if not openai_client:
        openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
    return openai_client


def analyze_page_content(
    links: List[Dict], high_priority_keywords: List[str], medium_priority_keywords: List[str], test_mode: bool = False
) -> List[Dict]:
    """Analyze links with pre-filtering to reduce API calls."""
    client = init_openai()

    links = _prepare_links(links, test_mode)

    # Process links in batches
    analyzed_links = []
    for i in range(0, len(links), config.BATCH_SIZE):  # Process 20 links at a time
        batch = links[i : i + config.BATCH_SIZE]

        try:
            analyzed_batch = _analyze_batch(client, batch, high_priority_keywords, medium_priority_keywords)
            analyzed_links.extend(analyzed_batch)
        except Exception as e:
            logger.error(f"Error analyzing batch: {e}")
            continue

    return analyzed_links


def _prepare_links(links: List[Dict], test_mode: bool) -> List[Dict]:
    """Prepare links for analysis, limiting count in test mode."""
    if test_mode:
        return links[: config.TEST_MAX_LINKS_PER_PAGE]
    return links


def _analyze_batch(
    client: OpenAI, links: List[Dict], high_priority_keywords: List[str], medium_priority_keywords: List[str]
) -> List[Dict]:
    """Analyze a batch of links using OpenAI."""

    prompt = _build_analysis_prompt(links, high_priority_keywords, medium_priority_keywords)

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert web content analyst who evaluates the relevance of web links and their context to specific keywords. Use your knowledge of language to consider synonyms, related terms, broader concepts, and semantic relationships when assessing relevance.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        logger.debug(f"OpenAI Response: {response}")

        # Extract JSON from response
        result = extract_json(response.choices[0].message.content)

        # filter to meet relevancy threshold
        filtered_links = filter_links(result, threshold=0.3)

        return filtered_links

    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return []


def filter_links(links, threshold=0.3):
    filtered = [link for link in links if link["relevancy"] >= threshold]
    return filtered


def _build_analysis_prompt(
    links: List[Dict], high_priority_keywords: List[str], medium_priority_keywords: List[str]
) -> str:
    """Build prompt for OpenAI analysis."""
    # Serialize the dynamic links data
    serialized_links = json.dumps(links, indent=4)

    # Define the example JSON strings with escaped curly braces
    example_format = """
    Example format:
    [
        {{
            "url": "https://www.example.com/contact",
            "relevancy": 1.0,
            "relevancy_explanation": "This link provides direct contact information, matching the high priority keyword 'Contact'.",
            "high_priority_keywords": ["Contact"],
            "medium_priority_keywords": [],
            "context": "Get in touch with us through our contact page."
        }}
    ]
    """

    example_input = """
    Here is an example of a set of input links:
    [
        {
            "url": "https://www.example.com/careers",
            "link_text": "Join Our Team",
            "context": "Explore career opportunities and apply to join our team."
        },
        {
            "url": "https://www.example.com/financials",
            "link_text": "Annual Financial Statements",
            "context": "Access our annual financial statements and reports."
        },
        {
            "url": "tel:+1234567890",
            "link_text": "Call Us",
            "context": "Get in touch via phone."
        },
        {
            "url": "mailto:contact@example.com",
            "link_text": "Email Us",
            "context": "Reach out via email."
        }
    ]
    """

    expected_output = """
    And this would be the expected output:
    [
        {
            "url": "https://www.example.com/careers",
            "relevancy": 0.6,
            "relevancy_explanation": "The link relates to 'Staff' as it refers to hiring new team members, matching the medium priority keyword.",
            "high_priority_keywords": [],
            "medium_priority_keywords": ["Staff"],
            "context": "Explore career opportunities and apply to join our team."
        },
        {
            "url": "https://www.example.com/financials",
            "relevancy": 0.9,
            "relevancy_explanation": "This link is highly relevant to the high priority keyword 'Financial Statement' as it provides access to annual financial statements.",
            "high_priority_keywords": ["Financial Statement"],
            "medium_priority_keywords": ["Finance"],
            "context": "Access our annual financial statements and reports."
        },
        {
            "url": "tel:+1234567890",
            "relevancy": 0.9,
            "relevancy_explanation": "Provides direct phone contact information, matching the high priority keyword 'Contact'.",
            "high_priority_keywords": ["Contact"],
            "medium_priority_keywords": ["Phone"],
            "context": "Get in touch via phone."
        },
        {
            "url": "mailto:contact@example.com",
            "relevancy": 0.9,
            "relevancy_explanation": "Provides direct email contact information, matching the high priority keyword 'Contact'.",
            "high_priority_keywords": ["Contact"],
            "medium_priority_keywords": ["Email"],
            "context": "Reach out via email."
        }
    ]
    """

    # Combine all parts into the final prompt
    prompt = f"""
    Analyze the following links and their context to determine their relevance to the given keywords.
    Assign a relevancy value (using the key "relevancy") between 0 and 1 based on how well each link relates to the keywords. 
    Think broadly and semantically by considering synonyms, related terms, and broader concepts associated with the keywords. 
    Do not include links that are not relevant (if the "relevancy" value is below 0.3).

    **Important:** Provide your output strictly in valid JSON format. Ensure all keys and string values are enclosed in double quotes, and do not use or escape single quotes inside the string values.

    High Priority Keywords: {', '.join(high_priority_keywords)}
    Medium Priority Keywords: {', '.join(medium_priority_keywords)}

    Links to analyze:
    {serialized_links}

    {example_format}

    In order to calculate the relevancy score, consider the following:
    - Consider synonyms, related terms, and broader concepts of the keywords.
    - Evaluate the semantic relationship between the link content and the keywords.
    - The more closely a link's content aligns with the keywords or their synonyms, the higher the score.
    - Use your understanding of language to identify relevant links beyond exact matches.
    - If a link indirectly relates to a keyword through a broader concept or related term, assign an appropriate relevancy score.

    {example_input}

    {expected_output}
    """
    return prompt
