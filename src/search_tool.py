import time
import logging
from ddgs import DDGS
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Setup logging to see when retries happen
from logging_config import get_logger

logging = get_logger(__name__)

class SearchTool:
    def __init__(self, max_results=5):
        self.max_results = max_results

    @retry(
        # Wait 2^x * 1 second between retries (2s, 4s, 8s...)
        wait=wait_exponential(multiplier=1, min=2, max=10), 
        # Stop after 3 failed attempts
        stop=stop_after_attempt(3),
        # Only retry on common network/rate limit errors
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.info(f"Rate limited. Retrying in {retry_state.next_action.sleep} seconds...")
    )
    def search(self, query: str) -> str:
        """
        Performs a web search with built-in retry logic for rate limits.
        """
        try:
            with DDGS() as ddgs:
                results = ddgs.text(
                    query, 
                    region='wt-wt', 
                    safesearch='off', 
                    max_results=self.max_results
                )
                
                if not results:
                    return f"No results found for query: {query}"

                formatted = [f"Title: {r['title']}\nSnippet: {r['body']}" for r in results]
                return "\n---\n".join(formatted)

        except Exception as e:
            # If it's a known rate limit string, we raise it to trigger the @retry
            if "ratelimit" in str(e).lower() or "429" in str(e):
                logger.warning("Search rate limit hit.")
                raise e 
            else:
                logger.error(f"Search failed: {e}")
                return f"Search error: {str(e)}"

# --- Usage in your Agent Loop ---
searcher = SearchTool()

def get_market_context(queries: list):
    context_results = []
    for q in queries:
        # Add a small polite delay between different queries to avoid triggering limits
        time.sleep(1.5) 
        result = searcher.search(q)
        context_results.append(result)
    return "\n\n".join(context_results)