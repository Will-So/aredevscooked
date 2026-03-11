"""Gemini API collector for market data."""

import json
import os
import re
import threading
import time

import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from google import genai
from google.genai import types
from aredevscooked.gemini_prompts import (
    create_headcount_prompt,
    create_job_postings_prompt,
    create_stock_data_prompt,
    create_summary_prompt,
)
from aredevscooked.config import GEMINI_CONFIG, VALIDATION


class GeminiCollector:
    """Collect market data using Gemini API with web search grounding."""

    def __init__(self, api_key: str | None = None):
        """Initialize Gemini collector.

        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be provided or set in environment")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = GEMINI_CONFIG["model"]

        # Configure grounding with Google Search if enabled
        tools = None
        if GEMINI_CONFIG.get("enable_grounding", True):
            tools = [types.Tool(google_search=types.GoogleSearch())]

        # Enable Google Search grounding for web-based queries
        self.generation_config = types.GenerateContentConfig(
            temperature=GEMINI_CONFIG["temperature"],
            tools=tools,
            # Note: No response_mime_type - use default for free-form text
            # We'll parse JSON from the response ourselves
        )

        # Setup logging directory
        self.log_dir = Path("logs/gemini_responses")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Track pending requests (thread-safe)
        self._pending_requests: dict[int, dict[str, Any]] = {}
        self._pending_lock = threading.Lock()

    def close(self):
        """Close the client and release resources."""
        if hasattr(self.client, "close"):
            self.client.close()

    def get_pending_request(
        self, thread_id: int | None = None
    ) -> dict[str, Any] | None:
        """Get info about a pending request.

        Args:
            thread_id: Thread ID to look up. If None, uses current thread.

        Returns:
            Dict with query_type, company_name, prompt, start_time or None
        """
        if thread_id is None:
            thread_id = threading.get_ident()
        with self._pending_lock:
            return self._pending_requests.get(thread_id)

    def _set_pending(self, query_type: str, company_name: str, prompt: str):
        """Mark a request as pending for the current thread."""
        thread_id = threading.get_ident()
        with self._pending_lock:
            self._pending_requests[thread_id] = {
                "query_type": query_type,
                "company_name": company_name,
                "prompt": prompt,
                "start_time": time.time(),
            }

    def _clear_pending(self):
        """Clear the pending request for the current thread."""
        thread_id = threading.get_ident()
        with self._pending_lock:
            self._pending_requests.pop(thread_id, None)

    def get_all_pending_requests(self) -> list[dict[str, Any]]:
        """Get all pending requests across all threads.

        Returns:
            List of pending request dicts with query_type, company_name, prompt, start_time
        """
        with self._pending_lock:
            return list(self._pending_requests.values())

    def _log_response(
        self,
        query_type: str,
        company_name: str,
        prompt: str,
        response_text: str,
        response_obj: Any,
    ):
        """Log Gemini API response to file for debugging.

        Args:
            query_type: Type of query (stock, headcount, jobs, summary)
            company_name: Company name or identifier
            prompt: The prompt sent to Gemini
            response_text: The text response from Gemini
            response_obj: The full response object from Gemini
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = company_name.replace(" ", "_").replace("/", "_")
        log_file = self.log_dir / f"{timestamp}_{query_type}_{safe_name}.log"

        with open(log_file, "w") as f:
            f.write(f"=== Gemini API Response Log ===\n")
            f.write(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"Query Type: {query_type}\n")
            f.write(f"Company: {company_name}\n")
            f.write(f"Model: {self.model_name}\n\n")

            f.write(f"=== PROMPT ===\n{prompt}\n\n")

            f.write(f"=== RESPONSE TEXT ===\n{response_text}\n\n")

            f.write(f"=== FULL RESPONSE OBJECT ===\n{response_obj}\n\n")

            # Try to extract and format usage metadata
            if hasattr(response_obj, "usage_metadata"):
                f.write(f"=== USAGE METADATA ===\n")
                f.write(
                    f"Prompt tokens: {response_obj.usage_metadata.prompt_token_count}\n"
                )
                f.write(
                    f"Total tokens: {response_obj.usage_metadata.total_token_count}\n"
                )

    def collect_headcount(
        self, company_name: str, target_date: str | None = None
    ) -> dict[str, Any]:
        """Collect employee headcount data for a company across multiple time periods.

        Args:
            company_name: Full company name
            target_date: Optional target date in YYYY-MM-DD format (currently unused)

        Returns:
            Dictionary with headcount data including:
            - current_headcount: Current headcount (backward compatible)
            - data_date: Date of current headcount (backward compatible)
            - source_urls: List of source URLs (backward compatible)
            - current: Dict with headcount, as_of_date, source_url, notes
            - one_year_ago: Dict with historical data (or None)
            - q1_2023: Dict with historical data (or None)

        Raises:
            ValueError: If headcount is out of plausible range
        """
        prompt = create_headcount_prompt(company_name, target_date)

        self._set_pending("headcount", company_name, prompt)
        try:
            api_start = time.time()
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt, config=self.generation_config
            )
            api_duration = time.time() - api_start
        finally:
            self._clear_pending()
        text = self._get_response_text(response)
        date_suffix = f"_{target_date}" if target_date else ""
        self._log_response(
            "headcount", f"{company_name}{date_suffix}", prompt, text, response
        )
        print(f"      [API call took {api_duration:.1f}s]")
        data = self._extract_json(text, response)

        # Normalize multi-period response for backward compatibility
        if "current" in data and isinstance(data["current"], dict):
            current_data = data["current"]
            data["current_headcount"] = current_data.get("headcount", 0)
            data["data_date"] = current_data.get("as_of_date", "")
            # Only use model-generated source_url if grounding URLs weren't found
            if "source_urls" not in data or not data["source_urls"]:
                source_url = current_data.get("source_url", "")
                data["source_urls"] = [source_url] if source_url else []

        # Validate headcount range
        headcount = data.get("current_headcount", 0)
        min_headcount = VALIDATION["headcount"]["min"]
        max_headcount = VALIDATION["headcount"]["max"]

        if not (min_headcount <= headcount <= max_headcount):
            raise ValueError(
                f"Headcount {headcount} outside plausible range "
                f"[{min_headcount}, {max_headcount}]"
            )

        return data

    def collect_stock_data(
        self, company_name: str, ticker: str, target_date
    ) -> dict[str, Any]:
        """Collect stock price data for a company.

        Args:
            company_name: Full company name
            ticker: Stock ticker symbol (e.g., "HCL.NS")
            target_date: Reference date; one-year-ago price is relative to this

        Returns:
            Dictionary with current_price, price_1_year_ago, dates, and source_urls

        Raises:
            ValueError: If current_price is not positive
        """
        prompt = create_stock_data_prompt(company_name, ticker, target_date)

        self._set_pending("stock", company_name, prompt)
        try:
            api_start = time.time()
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt, config=self.generation_config
            )
            api_duration = time.time() - api_start
        finally:
            self._clear_pending()
        text = self._get_response_text(response)
        self._log_response("stock", company_name, prompt, text, response)
        print(f"      [API call took {api_duration:.1f}s]")
        data = self._extract_json(text, response)

        current_price = data.get("current_price", 0)
        if current_price <= 0:
            raise ValueError(
                f"Stock price must be positive: {current_price}"
            )

        return data

    def collect_job_postings(self, company_name: str, jobs_url: str) -> dict[str, Any]:
        """Collect job posting counts for a company.

        Args:
            company_name: Full company name
            jobs_url: URL to the company's job board

        Returns:
            Dictionary with job posting data

        Raises:
            ValueError: If job count is negative
        """
        prompt = create_job_postings_prompt(company_name, jobs_url)

        self._set_pending("jobs", company_name, prompt)
        try:
            api_start = time.time()
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt, config=self.generation_config
            )
            api_duration = time.time() - api_start
        finally:
            self._clear_pending()
        text = self._get_response_text(response)
        self._log_response("jobs", company_name, prompt, text, response)
        print(f"      [API call took {api_duration:.1f}s]")
        data = self._extract_json(text, response)

        # Validate job count
        job_count = data.get("total_technical_jobs", 0)
        if job_count < 0:
            raise ValueError(f"Job posting count must be non-negative: {job_count}")

        return data

    def generate_summary(self, metrics_data: dict[str, Any]) -> str:
        """Generate AI-powered market summary.

        Args:
            metrics_data: Complete metrics data structure

        Returns:
            One-paragraph summary text
        """
        prompt = create_summary_prompt(metrics_data)

        # Note: Summary generation doesn't need grounding - it's analyzing provided data
        response = self.client.models.generate_content(
            model=self.model_name, contents=prompt, config=self.generation_config
        )
        text = self._get_response_text(response)
        self._log_response("summary", "market_summary", prompt, text, response)
        return text.strip()

    def _get_response_text(self, response) -> str:
        """Extract text from Gemini API response.

        Args:
            response: Gemini API response object

        Returns:
            Text content from the response

        Raises:
            ValueError: If text cannot be extracted from response
        """
        # Try direct .text attribute (most common)
        if hasattr(response, "text") and response.text is not None:
            return response.text

        # Try candidates structure
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and candidate.content:
                if hasattr(candidate.content, "parts") and candidate.content.parts:
                    part = candidate.content.parts[0]
                    if hasattr(part, "text") and part.text is not None:
                        return part.text

        raise ValueError(f"Could not extract text from Gemini response: {response}")

    def _resolve_redirect_url(self, redirect_url: str, retries: int = 2) -> str:
        """Resolve a Google redirect URL to its actual destination.

        Gemini returns temporary redirect URLs like
        'https://vertexaisearch.cloud.google.com/grounding-api-redirect/...'
        instead of actual source URLs. This method follows the redirect
        to get the real URL.

        Args:
            redirect_url: The redirect URL from grounding metadata
            retries: Number of retry attempts on failure

        Returns:
            The actual destination URL, or the original if resolution fails
        """
        for attempt in range(retries + 1):
            try:
                response = requests.head(redirect_url, allow_redirects=True, timeout=10)
                if response.url != redirect_url:
                    return response.url
                # If HEAD didn't follow redirect, try GET
                response = requests.get(
                    redirect_url, allow_redirects=True, timeout=10, stream=True
                )
                response.close()
                return response.url
            except requests.RequestException as e:
                if attempt < retries:
                    time.sleep(0.5)  # Brief pause before retry
                    continue
                print(
                    f"      [Warning: Failed to resolve URL after {retries + 1} attempts: {e}]"
                )
                return redirect_url
        return redirect_url

    def _extract_grounding_urls(self, response) -> list[str]:
        """Extract actual source URLs from grounding metadata.

        Args:
            response: Gemini API response object

        Returns:
            List of resolved source URLs from grounding chunks
        """
        urls = []
        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "grounding_metadata"):
                    metadata = candidate.grounding_metadata
                    # First try grounding_chunks (preferred source)
                    if (
                        hasattr(metadata, "grounding_chunks")
                        and metadata.grounding_chunks
                    ):
                        for chunk in metadata.grounding_chunks:
                            if hasattr(chunk, "web") and hasattr(chunk.web, "uri"):
                                redirect_url = chunk.web.uri
                                actual_url = self._resolve_redirect_url(redirect_url)
                                urls.append(actual_url)
                    # Fallback: extract from search_entry_point HTML if no chunks
                    if not urls and hasattr(metadata, "search_entry_point"):
                        entry_point = metadata.search_entry_point
                        if hasattr(entry_point, "rendered_content"):
                            html = entry_point.rendered_content
                            # Extract URLs from <a class="chip" href="..."> tags
                            chip_urls = re.findall(
                                r'<a\s+class="chip"\s+href="([^"]+)"', html
                            )
                            for redirect_url in chip_urls:
                                actual_url = self._resolve_redirect_url(redirect_url)
                                urls.append(actual_url)
        except Exception as e:
            print(f"      [Warning: Could not extract grounding URLs: {e}]")
        return urls

    def _extract_json(self, text: str, response=None) -> dict[str, Any]:
        """Extract JSON from Gemini response text.

        Handles responses that may have JSON in markdown code blocks or plain text.

        Args:
            text: Response text from Gemini
            response: Optional response object to extract grounding URLs from

        Returns:
            Parsed JSON as dictionary

        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        if not text:
            raise ValueError("Empty response text from Gemini")

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError(f"Could not extract JSON from response: {text[:200]}")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {e}")

        # Replace all source URLs with actual grounding URLs if available
        # This prevents the model from hallucinating URLs
        if response:
            grounding_urls = self._extract_grounding_urls(response)
            if grounding_urls:
                data["source_urls"] = grounding_urls
                # Also replace nested source_url fields (e.g., in current, one_year_ago, q1_2023)
                first_url = grounding_urls[0]
                for key in ["current", "one_year_ago", "q1_2023"]:
                    if key in data and isinstance(data[key], dict):
                        data[key]["source_url"] = first_url

        return data
