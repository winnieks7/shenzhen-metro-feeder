# Reproduction details

## Inputs and execution order

`research/input_manifest.json` records the original study's 41 extracted files with SHA-256 and ZIP CRC32, the Figshare file ID and dataset version. `research/CPTOND_archive_index.json` contains only the relevant Shenzhen members and original README. The factual April 2025 route registry is included for the `official_matched` variant.

The wrapper creates output folders and runs these steps in order:

```sh
python scripts/fetch_cptond_shenzhen.py  # once; or use the documented manual download
python scripts/test_geometry.py
python scripts/prepare_network.py
python scripts/validate_official.py
python scripts/coverage_analysis.py --grid --variants
python scripts/summarize_results.py
python scripts/make_figures.py
python scripts/check_revision_evidence.py
python scripts/make_method_schematic.py
python scripts/analyze_application_cases.py
python scripts/make_application_figure.py
```

For individual plotting scripts, ensure `paper/figures/` and `paper/qa/` exist. The wrapper creates both. The official-label comparison must precede the `official_matched` variant. All 31 scenarios must exist before summarization. Scenario files are recomputed, not reused merely because their filenames exist.

## Parameters and expected outputs

Baseline: 500 m Euclidean transfer radius, 5,000 m ordered distance along the bus polyline, and 300 m circular buffers around eligible bus stops. The grid combines radii 300/500/800 m, ride budgets 3,000/5,000/8,000 m and stop buffers 200/300/500 m (27 combinations). Variants use the broader ordinary-bus sample, any source metro point, finer buffer tessellation, or official-matched labels.

Expected sample: 325 station complexes; 1,231 core directions and 714 labels; 1,879 directions in the broader ordinary-bus sample. Each scenario table has 650 rows. The sensitivity summary has 54 rows and the variant summary has eight. They are parameter settings, not independent experiment replications.

The baseline count–coverage percentile gap reaches at least 20 percentage points at 54 inbound and 58 outbound stations. Xianhu Road and Shajing each have 28 inbound directions but approximately 8.11 and 26.03 square kilometres of union coverage. Persistent gaps in at least 22/27 grid settings occur at 11 inbound and eight outbound stations. The independent expression in `check_revision_evidence.py` checks 80 ordered-reachability boundary cases and the persistence counts.

## Table fields

| Field | Meaning |
|---|---|
| `station_id`, `name` | Analysis station identifier and source name |
| `x`, `y` | EPSG:32649 coordinates in metres |
| `direction` | `inbound`: bus to metro; `outbound`: metro to bus |
| `N`, `L` | Eligible service-direction count and complete label count |
| `A_km2` | Area of the union across eligible directions |
| `S_km2` | Sum of the within-direction union areas |
| `O` | Overlap index 1 − A/S; undefined when S = 0 |
| `served_points` | Distinct eligible bus-stop coordinates, not passengers |
| `B500_km2` | Union area outside the combined 500 m metro buffers |
| `positive20_n`, `negative20_n` | Number of 27 settings with signed percentile gaps ≥ +0.20 or ≤ −0.20 |

Percentiles use average ranks for ties. Top-65 comparisons also provide tie-inclusive sets. GeoJSON geometries use **EPSG:32649**, not longitude/latitude; transform them before using a geographic web map. Route-exclusive areas do not sum to total coverage and do not indicate removable service.

## Destination cases

Three cases are defined in `research/application_case_plan.md`. `ordered_paths.json` retains all baseline transfer-target candidates. `ride_distance_m` is the minimum ordered along-route distance among candidates within the transfer radius. Target eligibility applies to the exact named stop. Direction area and exclusive area apply to the selected direction's entire eligible footprint.

There are six case-direction rows, 54 radius/budget sensitivity rows and 42 geometry features. The destination map shows the three outbound cases at a common scale. No population, frequency or passenger-flow denominators are used.

## Reproduction comparisons

Check `release_manifest.json` before rerunning to verify the downloaded release. Regeneration may legitimately change figure metadata and very small floating-point details across operating systems or geometry-library builds; compare numerical tables with explicit tolerances. The exact package pins and recorded environment document the version used for the manuscript. The release validation record describes the checks actually performed for this code package.
