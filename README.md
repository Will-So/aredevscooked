# aredevscooked.com

Real-time IT Job Market Health Tracker - tracks hiring trends across IT consultancies, big tech, and AI labs.

## Overview

This project monitors the health of the tech job market through three tiers:
- **Low-End (IT Consultancies)**: Headcount trends and stock index for 7 major IT consultancies
- **Medium-End (Big Tech)**: Headcount trends for 5 major tech companies (Microsoft, Meta, Apple, Amazon, NVIDIA)
- **High-End (AI Labs)**: Job posting counts for 3 leading AI research labs (DeepMind, Anthropic, OpenAI)
- **Overall Verdict**: "Are Devs Cooked?" indicator showing Yes/Maybe/Not Today based on market health across all tiers

Data is collected daily via yfinance (stocks) and Gemini API with web search grounding (headcount, jobs, summary) and displayed on a static website with color-coded badges indicating market health.

## Quick Start

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/aredevscooked.git
cd aredevscooked

# Install dependencies (requires uv)
uv sync

# Set up environment variables
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

### Test the Website Locally

```bash
# Start local server (auto-opens browser on http://localhost:8000)
uv run python scripts/serve_website.py
```

### Collect Latest Data

```bash
# Run full data collection (stocks, headcount, job postings)
uv run python scripts/run_collection.py
```

This will:
- Collect stock prices for 7 IT consultancies via yfinance
- Collect headcount data for 12 companies
- Collect job postings for 3 AI labs
- Calculate changes vs historical baselines
- Generate humorous AI summary (70-word max)
- Save results to `data/processed/metrics_latest.json`

### One-Time Baseline Setup

```bash
# Backfill historical baseline data (only needed once)
uv run python scripts/backfill_baselines.py
```

Creates `data/processed/baselines.json` with data for:
- Q1 2023 (March 31, 2023)
- 1 year ago
- 30 days ago
- 1 day ago

## Development

### Run Tests

```bash
# Run all tests with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_orchestration.py

# Run in verbose mode
uv run pytest -v
```

### Format Code

```bash
# Format all Python files with Black
uv run black .

# Check formatting without changes
uv run black --check .
```

### Project Structure

```
aredevscooked/
├── .github/workflows/
│   └── daily-collection.yml      # GitHub Actions workflow (daily at 08:05 UTC)
├── data/
│   └── processed/
│       ├── metrics_latest.json   # Current metrics with changes
│       ├── metrics_history.json  # Daily snapshots
│       └── baselines.json        # Historical baseline data
├── src/aredevscooked/
│   ├── collectors/
│   │   └── gemini_collector.py   # Gemini API data collection
│   ├── processors/
│   │   ├── stock_processor.py    # Stock index calculations
│   │   ├── headcount_processor.py # Headcount change analysis
│   │   └── jobs_processor.py     # Job posting trends
│   ├── generators/
│   │   ├── badge_generator.py    # Badge classification logic
│   │   └── summary_generator.py  # AI-generated summaries
│   ├── models/
│   │   └── schemas.py            # Pydantic data models
│   └── utils/
│       ├── config.py              # Constants and thresholds
│       └── gemini_prompts.py      # Prompt templates
├── scripts/
│   ├── run_collection.py         # Main orchestration script
│   ├── backfill_baselines.py     # Historical baseline collector
│   └── serve_website.py          # Local development server
├── tests/                         # pytest test suite
├── website/
│   ├── index.html                # Static dashboard
│   ├── styles.css                # Dark theme styling
│   └── script.js                 # Frontend data loading
└── pyproject.toml                # uv project configuration
```

### Website Features

The static website (`website/` directory) displays:
- **Prominent Verdict Card**: Shows overall "Are Devs Cooked?" verdict (Yes/Maybe/Not Today) based on all metrics
- **Humorous AI Summary**: 70-word max contextual summary with witty commentary on market health
- **Stock Index**: Equal-weighted index tracking IT consultancies with individual stock prices
- **Per-Stock Changes**: 30-day and 1-year percentage changes for each stock
- **Color-Coded Badges**: Quick visual health assessment across all companies
- **Real-Time Data**: Auto-updates from `metrics_latest.json` with last updated timestamp

## Badge System

Health badges are assigned based on change thresholds:

### Headcount Changes (IT Consultancies & Big Tech)
- **Strong** 🟢: ≥ +5% growth
- **Neutral** ⚪: -5% to +5% (stable)
- **Reasonably Weak** 🟡: -5% to -10%
- **Weak** 🔴: -10% to -20%
- **Collapsing** 🔴🔴: ≤ -20%

### Job Posting Changes (AI Labs)
- **Strong** 🟢: ≥ +10 jobs
- **Neutral** ⚪: -10 to +10 jobs
- **Reasonably Weak** 🟡: -10 to -20 jobs
- **Weak** 🔴: -20 to -40 jobs
- **Collapsing** 🔴🔴: ≤ -40 jobs

Aggregate badges use a **"worst wins"** strategy - the most concerning badge among companies determines the tier's overall badge.

## Data Schema

### metrics_latest.json

```json
{
  "metadata": {
    "last_updated": "2025-12-26T08:05:00Z",
    "collection_status": "success"
  },
  "low_end": {
    "headcount": {
      "companies": {
        "HCLTech": {
          "current": 226640,
          "data_date": "2024-09-30",
          "changes": {
            "1_day_ago": {"value": -100, "pct": -0.04, "badge": "neutral"},
            "30_days_ago": {"value": -5000, "pct": -2.2, "badge": "neutral"},
            "1_year_ago": {"value": -15000, "pct": -6.6, "badge": "reasonably_weak"},
            "q1_2023": {"value": +696, "pct": +0.3, "badge": "neutral"}
          }
        }
      },
      "aggregate_badge": "reasonably_weak"
    },
    "stock_index": {
      "current_value": 92.7,
      "baseline_date": "2024-12-29",
      "changes": {
        "30_day": 5.09,
        "1_year": -7.3
      },
      "companies": {
        "HCLTech": {
          "ticker": "HCLTECH.NS",
          "current_price": 1650.5,
          "weight": 0.142857,
          "change_30_day": 8.5,
          "change_1_year": -5.2
        }
      },
      "aggregate_badge": "reasonably_weak"
    }
  },
  "medium_end": { /* ... */ },
  "high_end": { /* ... */ },
  "ai_summary": "Market shows mixed signals..."
}
```

## API Configuration

The project uses yfinance for stock data and Gemini API with web search grounding for headcount, job postings, and AI summary generation.

### Required Environment Variables

```bash
GEMINI_API_KEY=your_api_key_here  # Get from https://aistudio.google.com/
```

### API Usage

Daily collection makes approximately **16 Gemini API requests**:
- 12 headcount queries (7 consultancies + 5 big tech)
- 3 job posting counts (AI labs)
- 1 AI summary generation (humorous, 70-word max)

**Note**: Stock prices are collected via yfinance (no API quota usage)

**Free tier quota**: 1,500 requests/day (sufficient)

### Rate Limits

- Default: 1000 requests/minute (RPM)
- Collection runs concurrently using asyncio
- Typical runtime: ~26 seconds for full collection

## Deployment

### GitHub Actions

The project includes a GitHub Actions workflow (`.github/workflows/daily-collection.yml`) that:
- Runs daily at 08:05 UTC
- Collects all data
- Updates JSON files
- Commits changes to repository

### Setup GitHub Actions

1. Add `GEMINI_API_KEY` to repository secrets
2. Enable GitHub Actions in repository settings
3. Workflow will run automatically daily

### GitHub Pages

The static website (`website/` directory) can be served via GitHub Pages:

1. Go to repository Settings → Pages
2. Source: Deploy from branch
3. Branch: main
4. Folder: `/website`
5. Site will be live at `https://yourusername.github.io/aredevscooked/`

**Important**: The collection script automatically copies `metrics_latest.json` to the `website/` directory for GitHub Pages deployment. This ensures the website can load data without needing to access the `data/` directory.

## TDD Workflow

This project follows Test-Driven Development:

```bash
# 1. Write failing test
# Edit tests/test_*.py

# 2. Run test to confirm it fails
uv run pytest tests/test_*.py -v

# 3. Implement feature to make test pass
# Edit src/aredevscooked/*

# 4. Run test to confirm it passes
uv run pytest tests/test_*.py -v

# 5. Format code
uv run black .

# 6. Commit changes
git add .
git commit -m "feat: implement feature with tests"
```

## Data Sources

- **Stock Prices**: Yahoo Finance via yfinance library (direct API, not Gemini)
- **Headcount**: Company SEC filings, investor reports, earnings calls (via Gemini API with web search grounding)
- **Job Postings**: Greenhouse.io career pages (via Gemini API with web search grounding)
- **AI Summary**: Generated by Gemini API analyzing all metrics
- **Amazon Headcount**: Corporate-only workforce (excludes warehouse/fulfillment)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests first (TDD)
4. Implement feature
5. Format code (`uv run black .`)
6. Run tests (`uv run pytest`)
7. Commit changes (`git commit -m 'feat: add amazing feature'`)
8. Push to branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Data collection powered by [Gemini API](https://ai.google.dev/)
- Stock index inspired by equal-weighted indices
- Badge system designed for quick market health assessment
