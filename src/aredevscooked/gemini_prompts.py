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
    q1_2023 = "2023-03-31"

    additional_instruction = ""
    if company_name == "Amazon":
        additional_instruction = """
AMAZON NOTE: Amazon does not separately report corporate vs warehouse headcount in SEC filings so you will need to rely on other sources to get an estimate of corporate workers. 
If you see a number 
above 1 million employees, that's the number including hourly workers and you should not consider number."""

    return f"""Search for employee headcount data for {company_name} across multiple time periods.

IMPORTANT RULES:
1. Use QUARTERLY earnings reports or 10-K/10-Q SEC filings as primary sources
2. Each company reports headcount quarterly - find the closest quarterly report to each target date
3. If layoffs were announced AFTER the quarterly report date, subtract them and note this in the "notes" field
{additional_instruction}

Find headcount for these time periods (use closest available quarterly report):
1. CURRENT: Most recent quarterly report + any subsequent layoff adjustments
2. ONE YEAR AGO: Quarterly report closest to {one_year_ago}
3. Q1 2023: Quarterly report closest to {q1_2023}

Return ONLY a JSON object with this exact structure:
{{
  "company": "{company_name}",
  "current": {{
    "headcount": 0,
    "as_of_date": "YYYY-MM-DD",
    "notes": "e.g., 'Q3 2024 10-Q filing minus 5k Jan 2025 layoffs'"
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

Write a humorous but informative paragraph (MAX 60 words) about whether devs are actually cooked.

Context: Small changes like -3% headcount aren't bad news - that's just normal market dynamics.
Real concerns are double-digit declines, collapsing stock prices, or AI labs going on hiring freezes.
Be witty about whether the sky is actually falling or if this is just another day in tech.

Focus on:
1. IT consultancies: Headcount & stock trends
2. Big Tech: Headcount changes
3. AI labs: Job posting momentum

Here is some additional context about the metrics that might be useful:
IT Consultancy Stock Price Changes. These are companies like Infosys and TCS that provide relatively low value-add consultancy services. 
    - Strengths of Metric: It seems like they do work that is the closest analogue to LLMs. My guess is that if Generative AI is going to automate large portions of the tech workforce, we will see it in IT Consultancy stock prices first since the stock market is very forward-looking. 
    - Weaknesses of Metric: It’s plausible the companies that are most used to providing LLM-related services are also the most able to use LLMs to provide the services they are already providing more efficiently or by doing more layoffs. 
IT Consultancy Employment changes. 
    - Strengths of Metric: Robust to the possibility that IT Consultancies will cut headcount and provide LLM-based services directly. 
    - Weaknesses of Metric: Backwards looking. Many companies only start reducing headcount when their finances deteriorate. 
Big Tech Headcount
    - Strengths of Metric: They have enormous demand for Software and are quite good at adapting new technologies to their particular use case. They are very sensitive to their stock price and if they think they have an opportunity to cut their labor costs by XX, they will take it. 
    - Weaknesses of Metric: This would go down along with stock prices in a recession. A better metric would account for this by only counting declining headcount as bad if the stock is up or flat. I’m not going to do this now but I will probably make the change if it becomes relevant. 
AI Lab Open Positions. 
    - Strengths of Metric: Handles the AI 2027 case where the major AI labs keep the best technology for themselves in order to gain a strategic advantage. If that happens, the opportunity cost of hiring people will be so high they won’t want to spend any time doing it and new positions will open to zero. 
    Weaknesses of Metric: (1) Unfortunately Deepmind doesn’t have a web archive of job postings so for now we really only have Anthropic and OpenAI. And job openings are much more noisy than (2) This doesn’t cover the “AI as a normal technology” case where engineers are automatable for 99% of jobs but not for AI research/ safety. 

Return ONLY the paragraph text, no JSON or additional formatting. Also the "Not Today" status a reference to the game of thrones "What do you we say to the god of death? Not today!  So if you can include a reference to that that would be funnier. No more than 1 reference. Also don't refer to things as Red Wedding unless it's at least a "Weak". Reasonbly weak is not sufficient."""
