from pathlib import Path
import json

# This slice is generated from real public hospital names/coordinates and official Aomori healthcare-area names.
# The geometry is an approximation for demo purposes and is rebuilt from committed source values in the repo.

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"

if __name__ == "__main__":
    for name in [
        "facilities_aomori_hospital.json",
        "living_areas_aomori_healthcare.geojson",
        "accessibility_summary_aomori_hospital.json",
    ]:
        path = DATA_DIR / name
        if not path.exists():
            raise SystemExit(f"Missing required artifact: {path}")
    print("Aomori healthcare slice artifacts are already committed in backend/app/data.")
