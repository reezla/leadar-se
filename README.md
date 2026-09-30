# Swedish LiDAR Lead Finder

A focused internal tool for finding and ranking Swedish companies that may need
Norrpoint's handheld LiDAR scanners. The MVP searches official SCB company data,
explains why each company is relevant, and exports a HubSpot-ready CSV.

The SCB tab is the intended source. While SCB credentials are pending, a separate
**Crawl Allabolag** tab can read public segmentation listings (company name, org
number, SNI, employees, revenue). It does not collect named contacts or send outreach.

## What it does

- Filters companies by target segment, SNI prefix, geography, employee size,
  revenue size, and activity text.
- Includes presets for surveying, construction, technical consulting, mining,
  forestry, utilities, industry, and property management.
- Produces an explainable score rather than a black-box recommendation.
- Keeps incomplete records visible and labels missing data.
- Deduplicates exports by Swedish organization number.

## SCB access

SCB made Företagsregistret data free in 2025, but access requires accepting its
terms and receiving credentials. Contact `scbforetag@scb.se` and request the
company layout needed by this application. SCB's current API uses a client
certificate and limits responses to 2,000 rows and 10 requests per 10 seconds.

SCB is replacing the API in September 2026. Confirm the endpoint and request
schema in the onboarding material you receive, then set `SCB_API_URL`. All
source-specific behavior is isolated in `src/lead_finder/providers/scb.py`.

## Local setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Update `.env` with the API URL and absolute certificate paths supplied by SCB:

```dotenv
SCB_API_URL=https://the-endpoint-provided-by-scb
SCB_CERT_PATH=/absolute/path/client-certificate.pem
SCB_KEY_PATH=/absolute/path/client-key.pem
SCB_CERT_PASSWORD=
```

If SCB supplies a PKCS#12 file, convert it to PEM files according to SCB's
credential instructions. Do not commit certificates or `.env`.

Run the application:

```bash
streamlit run app.py
```

## Streamlit Community Cloud

The free Community Cloud tier hosts **public** apps: anyone with the URL can
open them. The GitHub repo can stay private if you grant Streamlit access.

1. Commit and push `requirements.txt` plus the current `app.py`.
2. Open [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. **Create app** → repository `reezla/leadar-se`, branch `main`, file `app.py`.
4. Set Python to **3.11**.
5. Add SCB secrets later in the Cloud app settings if you get credentials.
   Do not upload client certificates into the public app.

Run verification:

```bash
ruff check .
pytest
```

## How targeting works

Segment defaults live in `config/segments.yaml` and can be edited without code
changes. SNI prefixes in the UI are hard filters. Company size, matching words,
selected geography, and data freshness contribute to ranking.

Unknown employee or revenue data does not automatically exclude a company. It
is surfaced as a completeness warning so potentially useful leads are not lost
because the source only provides size classes or has a missing value.

Before using the list for sales, manually review the first 50–100 results:

1. Is the industry genuinely relevant to scanning?
2. Is there a plausible use case: interiors, infrastructure, underground work,
   volume calculations, forestry, scan-to-BIM, or facility documentation?
3. Does the company have enough operational scale to buy the equipment?
4. Is the company already present in HubSpot?

Use the review to adjust SNI prefixes, keywords, and weights.

## HubSpot import

Download the CSV from the application and import it as **Companies** in HubSpot.
Create these custom company properties before the first import:

- `Organization number` — single-line text, configured as unique if your HubSpot
  subscription supports unique custom properties.
- `Lead score` — number.
- `Lead score reasons` — multi-line text.
- `Industry codes (SNI)` — single-line or multi-line text.
- `Data completeness warnings` — multi-line text.
- `Lead source` and `Source retrieved at`.

Map `Company domain name` to HubSpot's standard domain property when populated.
It is HubSpot's preferred company deduplication key. Keep organization number as
the stable Swedish identifier, particularly for records without a website.

The handheld LiDAR SNI shortlist lives in `docs/sni-handheld-lidar.md`. The same
codes appear as clickable chips under the SNI prefixes field.

## Project structure

- `app.py`: Streamlit rendering and user interactions only.
- `src/lead_finder/use_company_search.py`: search orchestration.
- `src/lead_finder/providers/`: replaceable source adapters.
- `src/lead_finder/scoring.py`: local filtering and explainable ranking.
- `src/lead_finder/exporters/`: HubSpot CSV mapping.
- `config/segments.yaml`: editable target-market presets.
- `tests/`: fixture-driven provider, scoring, rate-limit, and export tests.

## Data and outreach guardrails

Allabolag's published terms restrict unauthorized copying and commercial reuse;
do not replace the SCB provider with a scraper without written permission or a
license. Preserve source and retrieval date for imported records.

If contact enrichment is added later, prefer official company websites and
generic business contacts. Respect robots.txt and website terms. Named-person
data and outreach require a documented lawful basis, privacy information,
retention rules, and an immediate suppression/opt-out process. Have Swedish
counsel confirm the outreach workflow before activation.
