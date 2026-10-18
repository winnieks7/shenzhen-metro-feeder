# Shenzhen metro feeder bus coverage

Reproducible analysis for **Beyond Service Counts: Spatial Reach and Destination Connections of Metro Feeder Buses in Shenzhen, China**, by Yefang Zhou, Junyao Zhang and Di Wang. This repository accompanies a manuscript prepared for CICTP 2027; it does not imply acceptance or publication.

The analysis compares service counts with directional spatial coverage in the June 2025 Shenzhen network. It uses the public CPTOND-2025 v2 dataset, with 325 metro station complexes, 1,231 retained bus-direction records and 714 complete service labels. It includes 27 parameter combinations, four definition variants and three destination cases.

## Reproduce

Use Python 3.12. The recorded study environment and package versions are in `results/environment.json` and `requirements-analysis.txt`. Computation uses a local CPU; no API key or GPU is required.

```sh
git clone https://github.com/winnieks7/shenzhen-metro-feeder.git
cd shenzhen-metro-feeder
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-analysis.txt
python scripts/verify_release.py
python scripts/run_reproduction.py --download
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell. The download retrieves only the Shenzhen ZIP members and the original data README via verified HTTP byte ranges. CRC32, member length and the study's SHA-256 checksums are checked. The national ZIP checksum is not independently checked because the full archive is not downloaded. If the server stops supporting range requests, download the exact v2 archive from Figshare and place its Shenzhen shapefiles in `data/CPTOND2025_Shenzhen/bus/` and `metro/`, then run without `--download`.

The workflow regenerates and overwrites derived outputs. Use a fresh checkout to compare against the released results. Detailed commands, parameter meanings and expected results are in [REPRODUCE.md](REPRODUCE.md).

## Included materials

- `scripts/`: data retrieval, sample construction, geometry tests, coverage calculations, sensitivity summaries, destination cases and plotting.
- `results/scenarios/`: 31 scenario tables, each with 325 stations × two journey directions.
- `results/`: baseline, sample/filtering records, station comparisons and summary tables.
- `results/application/`: six destination-direction rows, 54 sensitivity rows, ordered paths and 42 derived geometry features.
- `paper/figures/`: reproducible figures, including the parameter sensitivity plot retained outside the main manuscript.
- `research/`: the Shenzhen archive index, input checksums, case definitions and official-source provenance.

## Data and interpretation

Original data: [CPTOND-2025 v2](https://doi.org/10.6084/m9.figshare.29377427.v2), CC BY 4.0. Dataset article: [Wang et al. (2026), Scientific Data](https://doi.org/10.1038/s41597-025-06505-4). Raw shapefiles and the intermediate prepared network are generated locally and excluded from Git.

Distances are geometric proxies, not observed walking routes or travel times. Coverage measures area, not passengers, population served or service quality. Station and service counts describe the filtered historical dataset, not current Shenzhen operations. The destination cases provide service context; they do not validate passenger benefits or justify route withdrawal.

## Citation and license

Use [CITATION.cff](CITATION.cff) to cite the software. Cite the original dataset separately. Original code is MIT licensed; derived data and figures use CC BY 4.0 with source attribution. See [DATA_LICENSE.md](DATA_LICENSE.md) for third-party material.

## Acknowledgments

This research was supported by the Shandong Provincial Natural Science Foundation, China (Grant No. ZR2024QG174) and the National Natural Science Foundation of China (Grant No. 71874069).
