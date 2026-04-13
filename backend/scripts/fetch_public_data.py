from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlretrieve

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / 'app' / 'data'
RAW_DIR = DATA_DIR / 'raw'
RAW_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = {
    'ssdse_e_csv': 'https://www.nstac.go.jp/files/SSDSE-E-2025.csv',
    'ssdse_b_csv': 'https://www.nstac.go.jp/files/SSDSE-B-2025.csv',
    'prefectures_geojson': 'https://raw.githubusercontent.com/smartnews-smri/japan-topography/main/data/municipality/geojson/s0010/prefectures.json',
}

TARGETS = {
    'ssdse_e_csv': RAW_DIR / 'SSDSE-E-2025.csv',
    'ssdse_b_csv': RAW_DIR / 'SSDSE-B-2025.csv',
    'prefectures_geojson': RAW_DIR / 'prefectures.json',
}


def main() -> None:
    metadata = {'sources': []}
    for key, url in SOURCES.items():
        target = TARGETS[key]
        print(f'Downloading {url} -> {target}')
        urlretrieve(url, target)
        metadata['sources'].append({'key': key, 'url': url, 'path': str(target.relative_to(BASE_DIR))})

    metadata_path = RAW_DIR / 'source_metadata.json'
    metadata_text = json.dumps(metadata, ensure_ascii=False, indent=2)
    metadata_path.write_text(metadata_text, encoding='utf-8')
    (DATA_DIR / 'source_metadata.json').write_text(metadata_text, encoding='utf-8')
    print(f'Wrote {metadata_path}')
    print(f'Wrote {DATA_DIR / "source_metadata.json"}')


if __name__ == '__main__':
    main()
