"""Owner-approved airport snapshot; a stale or partially refreshed pin must fail."""
from pathlib import Path

import yaml


def test_airport_refresh_pin():
    root = Path(__file__).resolve().parents[1]
    artifacts = yaml.safe_load((root / "manifest.yaml").read_text())["artifacts"]
    airport = next(a for a in artifacts if a["id"] == "bts_ontime/L_AIRPORT.csv")
    assert airport["url"] == "https://www.transtats.bts.gov/Download_Lookup.asp?Y11x72=Y_NVecbeg"
    assert airport["sha256"] == "7a3c2a0bbcdc6951c2ae6eefe1e5739cfeb86f5016006cec49e146bb54b9466d"
    assert airport["size_bytes"] == 320236
    assert airport["license"] == "us-government-public-domain"
