# Norrpoint scanners: what each one is for

Norrpoint sells 9 FJDynamics scanners ([norrpoint.se/scanners](https://www.norrpoint.se/scanners), read 2026-10-12).
The machine-readable version the app uses is `config/scanners.yaml`. Edit that file to change how the
post-crawl analysis recommends products.

## Quick pick

| Scanner | Type | Pick it when the company… | Key facts |
| --- | --- | --- | --- |
| **P2** | Handheld SLAM | documents existing buildings, interiors, technical rooms, plants; scan-to-BIM | 0.7 kg, 70 m, 1.2 cm rel. / 3 cm abs., 200 000 pts/s, optional RTK |
| **P2 Vision+** | Handheld + thermal | does thermography, energy surveys or inspection with reports | LiDAR + RGB (2 × 48 MP) + thermal in one dataset, ±2 °C, Max = 640 × 512 |
| **S1** | SLAM, handheld/backpack/vehicle/drone | measures stockpiles, quarries, forest; outdoor/underground without GNSS | 120 m, 2 cm rel., 320 000 pts/s (Pro 640 000); 15 000 m³ ballast in 30 min |
| **S2** | Long-range SLAM | works in tunnels, mines, rail, roads, bridges, large sites | 1.8 kg, 120 m (MAX 300 m), 1.2 cm rel., no GNSS needed underground |
| **T1** | Hybrid mobile + tripod | is a survey/scanning firm needing mm detail plus fast coverage | 640 000 pts/s; ≤ 1 cm mobile; 4 mm @ 10 m on tripod; RTK/PPK built in |
| **X1** | Guided handheld with GNSS + 360° | documents many sites repeatedly (contractors, site managers, inspectors) | 0.9 kg, 384 000 pts/s, route guidance, issue marking, voice notes, cloud reports |
| **V4e** | Entry-level LiDAR | is small or starting with 3D scanning | ~0.89 kg, 50 m, 1 cm rel. / 3 cm abs., ≥ 5 h battery |
| **C1** | Indoor floor-plan scanner | needs floor plans of apartments, offices, premises (property, architects, fit-out) | 0.1–6 m, laser ±3 mm, 200 m² in ~3 min, editable DXF |
| **V100F** | GNSS rover + LiDAR | does GNSS/pole surveying, stakeout, earthworks, roads where sky is blocked | RTK 8 mm + 1 ppm, LiDAR ±5 cm @ 20 m without contact, IP65, 22 h RTK |

## How the app picks

Select companies and click **Generate leads**. For each one:

1. **Crawl** the company website (home, about, projects). Companies already crawled reuse
   their saved text instead.
2. **Analyze** right after the crawl (`src/lead_finder/analysis.py`):
   - With `OPENAI_API_KEY`: the model reads the site text against `config/scanners.yaml` and returns the
     main scanner, up to 2 alternatives, buyer type, customer fit, whether they already scan, quotes
     copied from the site, and a Swedish outreach angle. Product names outside the catalog and quotes
     not found in the site text are dropped.
   - Without a key, or if the call fails: the rules in `config/jobs.yaml`, matched against the
     name, SNI and the crawled text.
3. **Save** to `companies`: `recommended_product`, `alternative_products`, `buyer_type`,
   `customer_fit`, `product_analysis` (full JSON) and `analyzed_at`.
4. **Write the email**: the draft names the recommended scanner and uses the angle.

Buyer types:

- `performs_measurement`: they measure, scan or build on site → pitch the scanner.
- `orders_measurement`: project managers, client representatives, designers → pitch it as an option
  in their projects, or ask who measures for them.
- `not_relevant`: nothing physical to document → skip.

## Rules of thumb

- A firm that **already scans** (laserskanning, punktmoln, drone): T1 for accuracy, or P2 as a
  handheld complement for interiors and underground.
- A **survey firm doing GNSS work** (utsättning, maskinstyrning): V100F, with T1 as the alternative.
- **Small firms** (under 5 employees): V4e or C1 before P2.
- **Volumes** (täkt, lagerhögar): S1. **Tunnels and mines**: S2.
