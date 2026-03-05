# AEO Multi-Tenant Platform

A multi-tenant SaaS platform for Answer Engine Optimization (AEO) - tracking how brands appear in AI assistant responses.

## Features

- **Multi-tenant architecture** - Multiple brands, each with their own users and data
- **Keyword/Prompt tracking** - Track how your brand appears for specific AI prompts
- **Weekly automated scans** - Scheduled scans using Gemini API with grounding
- **Competitor analysis** - Compare your visibility against competitors
- **Content suggestions** - AI-generated blog post ideas to improve visibility
- **Weekly reports** - Automated reports with trends and recommendations

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (optional for local dev)
export GEMINI_API_KEY="your-gemini-api-key"  # Get from aistudio.google.com

# Run the app
python run.py
```

Default login:
- Email: `admin@aeoplatform.local`
- Password: `admin123`

## Architecture

```
aeoplatform/
├── app/
│   ├── models.py           # Database models (Tenant, User, Keyword, Scan, etc.)
│   ├── routes/             # Flask blueprints
│   │   ├── auth.py         # Login/register
│   │   ├── dashboard.py    # Main dashboard
│   │   ├── keywords.py     # Keyword management
│   │   ├── competitors.py  # Competitor tracking
│   │   ├── scans.py        # AEO scans
│   │   └── reports.py      # Weekly reports
│   ├── services/           # Business logic
│   │   ├── aeo_scanner.py      # Gemini API scanning
│   │   ├── keyword_research.py # Keyword discovery
│   │   ├── report_generator.py # Report generation
│   │   └── scheduler.py        # APScheduler jobs
│   └── templates/          # Jinja2 templates
├── config.py               # Configuration
├── requirements.txt
├── run.py                  # Entry point
└── README.md
```

## Data Model

- **Tenant** - A brand/organization
- **User** - Belongs to a tenant (admin or regular user)
- **Keyword** - Prompts/questions to track for AEO
- **Competitor** - Competitor brands to compare against
- **Scan** - A run of the AEO scanner
- **ScanResult** - Individual results per keyword
- **WeeklyReport** - Aggregated weekly performance
- **ContentSuggestion** - AI-generated content ideas

## How It Works

1. **Setup** - User registers their brand, adds website URL
2. **Keywords** - Add keywords manually or auto-discover from website
3. **Competitors** - Add competitor brands to track
4. **Scan** - Run scans to check AI visibility (Gemini API with grounding)
5. **Reports** - Weekly automated reports with trends
6. **Content** - Get suggestions for AEO-optimized blog posts

## API Keys

- **Gemini API** (optional but recommended): Get free key from [aistudio.google.com](https://aistudio.google.com)
  - Enables real AI visibility scanning
  - Without it, falls back to web search approximation

## Deployment

For production:
```bash
export SECRET_KEY="your-secret-key"
export DATABASE_URL="postgresql://..."
export GEMINI_API_KEY="your-key"
export FLASK_ENV="production"

gunicorn -w 4 -b 0.0.0.0:8000 "run:app"
```

## Roadmap

- [ ] Stripe integration for subscriptions
- [ ] More AI model support (OpenAI, Anthropic)
- [ ] Content editor with AEO scoring
- [ ] Email notifications for reports
- [ ] API for external integrations
- [ ] White-label options