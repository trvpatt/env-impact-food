"""Load reference data (cuisines, avatars, quotes, plans) into the database. Safe to re-run.

Usage (from backend/):
    python -m scripts.seed_reference_data [path/to/reference_data.json]

Plan provider price ids are environment-specific, so they come from config (env or .env):
    PLAN_PRICE_IDS="plus_monthly=price_123,plus_yearly=price_456"
"""

import json
import sys
from pathlib import Path

from sqlmodel import Session

from app.core.config import get_settings
from app.core.db import get_engine
from app.models import Avatar, Cuisine, Plan, Quote

DEFAULT_PATH = Path(__file__).parent / "data" / "reference_data.json"
MODELS = {"cuisines": Cuisine, "avatars": Avatar, "quotes": Quote, "plans": Plan}


def _price_ids() -> dict[str, str]:
    pairs = (p.split("=", 1) for p in get_settings().plan_price_ids.split(",") if "=" in p)
    return {k.strip(): v.strip() for k, v in pairs}


def main(path: Path) -> None:
    data = json.loads(path.read_text())
    price_ids = _price_ids()
    with Session(get_engine()) as session:
        for key, model in MODELS.items():
            for row in data.get(key, []):
                if key == "plans":
                    existing = session.get(Plan, row["id"])
                    current = existing.provider_price_id if existing else None
                    row = {**row, "provider_price_id": price_ids.get(row["id"], current)}
                session.merge(model(**row))
            print(f"{key}: {len(data.get(key, []))} rows")
        session.commit()


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH)
