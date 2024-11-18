# Web Crawler - Waverly Mandel

A Python web crawler project with Gemini LLM link prioritization and sqlite storage.

Codebase walkthru and demo: https://www.loom.com/share/ee7be5da393c484083358897b8ea28e5?sid=796675bd-fa35-443a-8d00-e42a36508c48

## Core Approach

### 1. Architectural Evolution & Choices

#### Initial Approach

Originally implemented as a simple HTML parser that passed entire page contents to Gemini for analysis. While functional, this evolved into a more sophisticated recursive crawler to better handle site hierarchy and content relationships.

#### Current Implementation: Depth-First Search (DFS)

The crawler uses a recursive DFS approach with the following characteristics:

- Maintains depth control to prevent infinite recursion
- Tracks visited URLs to avoid cycles
- Processes each page's links before moving to sibling pages
- Integrates Gemini analysis for intelligent path selection

#### Future Scaling Paths

**Medium Term: Hybrid Architecture**

- Priority queue for intelligent crawling
- Basic parallelization capabilities
- Enhanced metrics and monitoring
- Improved rate limiting and resource management

**Long Term: Distributed Architecture**

- Multiple workers across machines
- Message queue for job distribution
- Sophisticated priority algorithms

#### Architecture Trade-offs

**Current DFS Approach**

Pros:

- Simple to implement and understand
- Memory efficient (stack-based)
- Good for deep exploration
- Natural for priority-based exploration

Cons:

- Can get stuck in deep paths
- Not easily parallelizable
- Sequential processing can be slow
- Can miss broad context of certain pages


#### Implementation Notes

The current implementation uses Python's built-in capabilities and SQLite for storage, making it suitable for an MVP while providing clear paths for scaling. Future versions could incorporate Redis for job queuing, multiple worker processes, and distributed storage solutions.

## Gemini AI Implementation

### Link Analysis
- Uses AI to analyze link context and assign relevancy scores
- Stores relevancy and context for later querying
- Enables filtering high-priority content via the API

### Areas for Improvement
1. **Intelligent keyword handling**:
   - Leverage the LLM to suggest new keywords based on content being crawled or synonyms. Some ideas:
   ```
   def generate_synonyms(keyword: str, context: str = "") -> List[str]:
      prompt = f"Generate a list of synonyms and related terms for the keyword '{keyword}' in the context of {context}."
      response = gemini_model.generate_content(prompt)
      synonyms = extract_json(response.text).get('synonyms', [])
      return synonyms
      
   def suggest_keywords(content: str, existing_keywords: List[str]) -> List[str]:
      prompt = f"Analyze the following content and suggest new relevant keywords related to government financial information, excluding existing keywords {existing_keywords}.\n\nContent:\n{content}"
      response = gemini_model.generate_content(prompt)
      suggested_keywords = extract_json(response.text).get('keywords', [])
      return suggested_keywords

    def categorize_keywords(keywords: List[str]) -> Dict[str, List[str]]:
      prompt = f"Categorize the following keywords into relevant categories related to government financial information:\n\nKeywords: {', '.join(keywords)}\n\nProvide the categories and associated keywords in JSON format."
      response = gemini_model.generate_content(prompt)
      categorized_keywords = extract_json(response.text)
      return categorized_keywords
    ```

2. **True Link Prioritization**:
   - Implement a priority queue for crawling
   - Use relevancy scores to determine crawl order
   - Add depth-limiting based on relevancy thresholds

3. **Current Limitations**:
   - Crawls in HTML document order
   - Relevancy scores only used for filtering results
   - No dynamic path prioritization
   - No category tags

## Key Components

- `Crawler`: Manages recursive page traversal and depth control
- `GeminiAnalyzer`: Handles AI-powered content analysis and link prioritization
- `Database`: Stores processed pages and prioritized links

## Configuration

The crawler can be configured with:

- High priority keywords (e.g., "ACFR", "Budget", "Financial Report")
- Medium priority keywords (e.g., "Finance", "Treasury", "Department")
- Maximum crawl depth
- Rate limiting settings
- Database storage options

## Notes on process, structure, and tradeoffs

1. Approach to LLM integration: Originally, I experimented with passing the entire HTML contents of a page to the LLM and allowing the model to extract links and assign relevancy. This was a simple approach, although I had to truncate the length of the html content for testing purposes and so that I could remain in gemini's free tier. I wanted to try using beautiful soup to extract links with a context window around them and passing those links to gemini for analysis. If I were to pursue this project further, I would try generating embeddings for each page and using a vector database to store and query the embeddings.

2. Eval and context: To improve the prompt further, I would provide a few example html documents and their expected outputs (the links and relevancy scores), so that the model is more likely to return the correct output format.
3. Prompt engineering: I played around with the prompt to get better results. Developing a test set to compare the results of my prompt to the expected output would help me improve the prompt further.
4. Web scraping: I noticed a few bugs come up with the urls provided. First, the bozeman url was a redirect, which initially caused the crawler to fail - it required adjusting the headers. Third, the https://boerneisd.net/ was timing out. I noticed that adding a 'www' to the url seemed to fix the issue. In order to deal with that, I added a block of logic in the exponential backoff function that tries to remove or add a www from the url and retry.

5. Parameterization: I added the ability to pass in custom high and medium priority keywords. This allows the crawler to be more flexible and useful for different use cases. Using high and medium priority keywords might not be necessary, I would look to tweak this as part of the prompt engineering

6. Testing - I added unit tests to experiment at the end. Originally, I focused on getting a working prototype and then did manual testing of the individual components. Going forward, I would build a unit test suite first, and consider my eval testing framework / test set before beginning development (I like to use a modified test-driven development approach)

7. Dynamic content: would need to use a headless browser like Selenium to handle dynamic content.

8. Parallel processing: I did not implement parallel processing in this prototype, but considering how to further leverage batching and async processing may help improve the performance of the crawler.

9. Error handling: covered basic use cases and the errors that came up based on the example urls, but would want to implement more robust error handling, logging and o11y for a production system.

10. Rate limiting: could be more robust

11. LLM model: I used the free tier of gemini, but would ideally implement langchain so that i could trade out different models and see which is best suited to this task.

## Prerequisites

- Python 3.7 or higher
- `make` command-line tool

## Setup

1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Create a `.env` file with your Gemini API key:

```bash
GEMINI_API_KEY=your_key_here
```

### Daily Development

Every time you open a new terminal to work on this project:

```bash
# On Unix/MacOS:
source venv/bin/activate

# On Windows:
.\venv\Scripts\activate

# You can also run this to see the activation command:
make activate
```

# Before each crawl, it's recommended to clear the database:

```bash
make clear-db
```

# Basic Crawl

Run with default keywords (defined in config.py):

```bash
make crawl
```

# Custom Keywords

Run with custom high-priority keywords:

```bash
make crawl ARGS="--high-priority Budget,ACFR,Finance"
```

# Run with both custom high and medium priority keywords:

```bash
make crawl ARGS="--high-priority Budget,ACFR --medium-priority Staff,Contact"
```

# Run api 
```bash
make run-api  # This command exists in Makefile but isn't documented
```

# Run tests
```bash
make test
```

### Default Keywords

If no keywords are provided via command line:

- High Priority: Contact, ACFR, Budget, Financial Report, Annual Report, Fiscal Year, Financial Statement
- Medium Priority: Finance, Director, Department, Contact, Staff, Treasury

## Configuration

Default settings and keywords can be modified in `src/web_crawler/config.py`.


## Project Structure

```
webcrawler-demo/
│
├── src/web_crawler/     # Source code
│   ├── crawler.py       # Main crawler implementation
│   ├── utils.py         # Utility functions
│   └── config.py        # Configuration settings
│
└── tests/              # Test files
    └── test_crawler.py
```

## Adding New Dependencies

With your virtual environment activated:

```bash
pip install package-name
```

## Troubleshooting

If you encounter any issues with your virtual environment:

```bash
# Remove everything and start fresh
make clean
make
```

## Core Dependencies

- requests: HTTP library for making web requests
- beautifulsoup4: HTML parsing library
- pytest: Testing framework
- black: Code formatter

## Development Notes

- Always ensure your virtual environment is activated before running commands
- The project uses a simple structure without package management files (no setup.py or requirements.txt)
- Dependencies are installed directly through the Makefile

## Testing the Crawler

The crawler supports a test mode for quick verification of the entire pipeline without processing too many pages.

### Test Mode Features

- **Limited Crawling**: Only processes a small number of pages and links
- **Test URLs**: Uses simplified test URLs instead of production seed URLs
- **Clear Logging**: Shows progress and limits during crawling

### Configuration

Test mode settings are defined in `src/web_crawler/config.py`:
```python
# Testing Configuration
TEST_MODE = False  # Default to production mode
MAX_LINKS_PER_PAGE = 3  # Only process top 3 links per page when testing
MAX_TOTAL_PAGES = 5    # Stop after crawling 5 pages total when testing

# Test URLs used in test mode
TEST_URLS = [
    "https://example.com",
    "https://httpbin.org/html"
]

# Production URLs used in normal mode
SEED_URLS = [
    "https://bozeman.net/",
    # Add other production URLs here
]
```

### Running Tests

To run the crawler in test mode:
```bash
make crawl ARGS="--test"
```

To run in production mode:
```bash
make crawl
```

### Test Mode Behavior

1. **Page Limits**
   - Stops after crawling `MAX_TOTAL_PAGES` total pages
   - Shows progress: "Processing page X of Y"

2. **Link Limits**
   - Only processes `MAX_LINKS_PER_PAGE` links from each page
   - Shows original vs limited link counts

3. **URL Selection**
   - Uses `TEST_URLS` instead of `SEED_URLS`
   - Simpler URLs for predictable testing

### Example Output
```
🔬 Running in TEST mode with limited crawling
🔬 Using 2 test URLs
📊 Processing page 1 of 5
🔍 Found 20 raw links on https://example.com
🔬 Test mode: Limited from 20 to 3 links
...
🛑 Reached maximum test pages limit (5)
```

This test mode is useful for:
- Quick verification of the crawler pipeline
- Testing changes without extensive crawling
- Development and debugging

```
