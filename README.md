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
- Maps a Norrpoint or Metricop product family when outreach is drafted.
- Keeps incomplete records visible and labels missing data.
- Deduplicates exports by Swedish organization number.

## SCB access

Search uses [SCB:s allmänna företagsregister](https://apiafr.scb.se/). Every
request sends the API key in the `X-API-Key` header. Set `SCB_API_URL` to
`https://apiafr.scb.se` and `SCB_API_KEY` to the key SCB issued.

The register accepts one filter per request. SNI prefixes are expanded to exact
5-digit codes and loaded from `/v1/juridiskaenheter/naringsgren/{code}`. County,
municipality, employee size, and name text are applied locally. Revenue is not
included in those list responses, so the revenue fields do not narrow SCB results.

## Local setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Update `.env` with the API key supplied by SCB:

```dotenv
SCB_API_URL=https://apiafr.scb.se
SCB_API_KEY=your-api-key
```

Do not commit `.env`.

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
5. Add root-level secrets in the Cloud app settings, then reboot the app:

   ```toml
   SCB_API_KEY = "..."
   OPENAI_API_KEY = "sk-..."
   ```

   Do not commit either key.

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

Search does not pick a product. Download the HubSpot CSV as soon as companies
are listed if you only need the ranked lead list. Product matching runs when
outreach is drafted: primary SNI, company name, and activity text tag a job
and recommend a Norrpoint or Metricop family. Secondary SNI codes do not pick
the product. Unclear codes without name evidence stay `needs review`. Rules
live in `config/products.yaml` and `config/jobs.yaml`.

Before using the list for sales, manually review the first 50–100 results:

1. Is the industry genuinely relevant to scanning?
2. Is there a plausible use case: interiors, infrastructure, underground work,
   volume calculations, forestry, scan-to-BIM, or facility documentation?
3. Does the company have enough operational scale to buy the equipment?
4. Is the recommended product family actually supported by the evidence?
5. Is the company already present in HubSpot?

Use the review to adjust SNI prefixes, keywords, job rules, and weights.

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
- After outreach drafts: `Recommended brand`, `Recommended job`,
  `Recommended product`, `Alternative product`, `Match confidence`,
  `Match evidence`, and `Match status`. These columns are omitted from the CSV
  until a draft has been generated.

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
- `src/lead_finder/matching.py`: Norrpoint and Metricop product rules.
- `src/lead_finder/exporters/`: HubSpot CSV mapping.
- `config/segments.yaml`: editable target-market presets.
- `config/products.yaml` and `config/jobs.yaml`: product families and job rules.
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
