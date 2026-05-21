"""Gemini API prompt templates for data collection."""

from datetime import date, timedelta
from typing import Any


def create_headcount_prompt(company_name: str, target_date: str | None = None) -> str:
    """Create prompt for collecting employee headcount data across multiple time periods.

    Args:
        company_name: Full company name (e.g., "Microsoft")
        target_date: Optional target date in YYYY-MM-DD format (currently unused,
            kept for backward compatibility)

    Returns:
        Formatted prompt string for Gemini API
    """
    today = date.today()
    one_year_ago = (today - timedelta(days=365)).strftime("%Y-%m-%d")
    thirty_days_ago = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    q1_2023 = "2023-03-31"

    additional_instruction = ""
    if company_name == "Amazon":
        additional_instruction = """
AMAZON NOTE: Amazon does not separately report corporate vs warehouse headcount in SEC filings.
You MUST use third-party estimates (stockanalysis.com, mlq.ai, news sources) to estimate corporate workers only.
- If you see a number above 1 million employees, that is the total including hourly warehouse workers — do NOT use it.
- Known corporate headcount milestones to anchor your estimates:
  - Q1 2023: ~385,000 corporate employees (before 2023 layoffs)
  - Jan 2023: ~18,000 layoffs announced
  - Jan 2024: ~27,000 layoffs announced (tech and corporate roles)
  - Late 2025 / Early 2026: ~14,000–30,000 further layoffs announced
- Search for: "Amazon corporate headcount [YEAR]", "Amazon white-collar employees", "Amazon layoffs corporate [YEAR]"
"""

    return f"""Search for employee headcount data for {company_name} across multiple time periods.

IMPORTANT RULES:
1. Use QUARTERLY earnings reports or 10-K/10-Q SEC filings as primary sources
2. Each company reports headcount quarterly - find the closest quarterly report to each target date
3. If layoffs were announced AFTER the quarterly report date, subtract them and note this in the "notes" field
4. Each time period will likely show a DIFFERENT headcount due to layoffs and hiring — do NOT use the same number for multiple periods unless your research specifically confirms no change occurred. Find period-specific sources for each.
{additional_instruction}

Find headcount for these time periods:
1. CURRENT: Most recent quarterly report + any subsequent layoff/hiring adjustments
2. 30 DAYS AGO ({thirty_days_ago}): Use the SAME quarterly report base as CURRENT, but only subtract layoffs or hiring changes announced on or before {thirty_days_ago}. Do NOT subtract events announced after that date. This must be a non-zero number — if no adjustments apply before {thirty_days_ago}, use the raw quarterly figure. Example: if current = Q1 2026 (77,986) minus layoffs announced May 20, and {thirty_days_ago} is April 20 (before those layoffs), then 30_days_ago = 77,986.
3. ONE YEAR AGO: Quarterly report closest to {one_year_ago}
4. Q1 2023: Quarterly report closest to {q1_2023}

Return ONLY a JSON object with this exact structure:
{{
  "company": "{company_name}",
  "current": {{
    "headcount": 0,
    "as_of_date": "YYYY-MM-DD",
    "notes": "e.g., 'Q3 2024 10-Q filing minus 5k Jan 2025 layoffs'"
  }},
  "30_days_ago": {{
    "headcount": 0,
    "as_of_date": "{thirty_days_ago}",
    "notes": "e.g., 'Same base as current: Q1 2026 77,986 — layoffs announced after {thirty_days_ago} not subtracted'"
  }},
  "one_year_ago": {{
    "headcount": 0,
    "as_of_date": "YYYY-MM-DD",
    "notes": "e.g., 'Q4 2023 earnings report'"
  }},
  "q1_2023": {{
    "headcount": 0,
    "as_of_date": "YYYY-MM-DD",
    "notes": "e.g., 'FY2023 10-K filing'"
  }},
  "confidence": "high"
}}

RULES:
- headcount must be integers between 1,000 and 2,000,000
- as_of_date is when the headcount number is valid (after any layoff adjustments)
- notes should explain the source and any adjustments made (e.g., layoffs subtracted)
- confidence: "high" (SEC/official filings), "medium" (reputable news), "low" (estimates)

If data for a time period is unavailable, use null for that period's object."""


def create_job_postings_prompt(company_name: str, jobs_url: str) -> str:
    """Create prompt for collecting job posting counts.

    Args:
        company_name: Full company name (e.g., "DeepMind")
        jobs_url: URL to the company's job board

    Returns:
        Formatted prompt string for Gemini API
    """
    return f"""Search {jobs_url} and count only technical roles.

Technical roles include:
- Engineering (Software Engineer, ML Engineer, etc.)
- Research (Fellow, Research Scientist, Applied Scientist, etc.)
- Technical roles with AI, ML, Data Science in the title

Ignore non-technical roles like:
- HR, Recruiting, People Operations
- Marketing, Sales, Business Development
- Operations, Finance, Legal

Return ONLY a JSON object with this exact structure:
{{
  "company": "{company_name}",
  "total_technical_jobs": 0,
  "job_titles": ["Job Title 1", "Job Title 2", "..."],
  "collection_date": "YYYY-MM-DD"
}}

Replace placeholder values with actual data. Include a representative sample of job titles (up to 10).
Total technical jobs should be a non-negative integer."""


def create_stock_data_prompt(company_name: str, ticker: str, target_date: date) -> str:
    """Create prompt for collecting stock price data.

    Args:
        company_name: Full company name (e.g., "HCLTech")
        ticker: Stock ticker symbol (e.g., "HCL.NS")
        target_date: The reference date; one-year-ago price will be relative to this date

    Returns:
        Formatted prompt string for Gemini API
    """
    one_year_ago = (target_date - timedelta(days=365)).strftime("%Y-%m-%d")
    return f"""Look up stock price data for {company_name} ({ticker}).

Find:
1. The most recent closing price (current_price) and its date (current_date)
2. The closing price on or nearest to {one_year_ago} (price_1_year_ago) and that date (price_1_year_ago_date)

Return ONLY a JSON object with this exact structure:
{{
  "company": "{company_name}",
  "ticker": "{ticker}",
  "current_price": 0.0,
  "current_date": "YYYY-MM-DD",
  "price_1_year_ago": 0.0,
  "price_1_year_ago_date": "YYYY-MM-DD",
  "source_urls": ["url1"]
}}

Prices must be positive numbers."""


def create_summary_prompt(metrics_data: dict[str, Any]) -> str:
    """Create prompt for generating market summary.

    Args:
        metrics_data: Complete metrics data structure with all three tiers

    Returns:
        Formatted prompt string for Gemini API
    """
    return f"""Based on this IT job market data:

{metrics_data}

Write an informative paragraph (MAX 50 words) about whether devs are actually cooked.

Context: Small changes like -3% headcount aren’t bad news - that’s just normal market dynamics.
Real concerns are double-digit declines, collapsing stock prices, or AI labs going on hiring freezes.

For each metric, answer the specific question it is designed to test:
1. IT consultancies (stock prices): Is the market already pricing in AI automation of low-value IT consultancy work? Declining stocks = investors believe AI will replace the lower-skilled outsourced work these firms depend on. This is a narrow signal about that segment — do NOT generalize it to broad investor panic or claims about the overall labor market.
2. Indeed Job Postings Index: Are companies already signaling they want fewer developers? Closing job postings is the first action taken before actual layoffs — this is a leading indicator of intent.
3. Big Tech headcount: Are large companies actually cutting developer labor costs via AI? Labor is 40-60% of big tech costs; these firms will aggressively cut if AI enables it.
4. AI lab open positions: Are we seeing the “AI 2027” hoarding pattern? If labs keep the best AI for strategic advantage, the opportunity cost of hiring skyrockets — postings dropping to zero confirms this scenario.

Return ONLY the paragraph text, no JSON or additional formatting."""


def create_joke_candidates_prompt(summary: str, metrics_data: dict[str, Any]) -> str:
    """Create prompt for generating 10 candidate jokes about the market data.

    Args:
        summary: The factual summary paragraph (no humor)
        metrics_data: Complete metrics data structure with all tiers

    Returns:
        Formatted prompt string for Gemini API
    """
    return f"""You are a comedy writer for a tech industry newsletter called "Are Devs Cooked?"

Here is today's factual market summary:
{summary}

Here is the underlying data:
{metrics_data}

Generate exactly 10 short jokes (1-2 sentences each) about whether software developers are "cooked" (doomed) based on this data. Each joke should be a standalone quip that could be appended to the summary paragraph.

Guidelines:
- Vary the style: wordplay, analogies, pop culture references, absurdist humor, dry wit
- The "Not Today" status is a reference to Game of Thrones ("What do we say to the god of death? Not today!"). If the data suggests devs are NOT cooked, try to work in a reference to this in at least one joke.
- Don't refer to things as a "Red Wedding" unless the situation is at least "Weak" severity. "Reasonably weak" is not sufficient for Red Wedding references.
- Keep each joke punchy and under 2 sentences

Return a numbered list (1-10), one joke per line. No other text or formatting."""


def create_joke_evaluation_prompt(summary: str, joke_candidates: str) -> str:
    """Create prompt for evaluating and selecting the funniest joke.

    Args:
        summary: The factual summary paragraph for context
        joke_candidates: The numbered list of 10 candidate jokes

    Returns:
        Formatted prompt string for Gemini API
    """
    return f"""You are a comedy editor selecting the best joke for a tech newsletter called "Are Devs Cooked?"

Here is today's summary paragraph (the joke will be appended after this):
{summary}

Here are 10 candidate jokes:
{joke_candidates}

Evaluate each joke on:
1. Relevance to the actual data
2. Wit and cleverness
3. Surprise factor / unexpectedness
4. How well it flows when appended to the summary paragraph above

Select the single funniest joke. You may lightly edit it for better flow with the summary if needed.

Return ONLY the text of the winning joke. No numbering, no explanation, no other text."""
