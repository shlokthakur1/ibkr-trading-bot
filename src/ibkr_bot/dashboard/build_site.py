"""Build the dashboard as a static site for GitHub Pages.

Copies static/ (index.html) and writes each exported JSON file at the same relative path the
FastAPI app serves it on — api/status, api/metrics, ... — so the one index.html works unchanged
whether it's served by uvicorn locally or from a GitHub Pages subpath. Run with:

    python -m ibkr_bot.dashboard.build_site --data published/dashboard --out _site
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .api import ROUTE_FILES

STATIC_DIR = Path(__file__).parent / "static"


def build_site(data_dir: str | Path, out_dir: str | Path) -> None:
    """Fails loudly on a missing export file rather than publishing a half-empty page."""
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    missing = [name for name in ROUTE_FILES.values() if not (data_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"{data_dir} is missing {', '.join(missing)} — export a run there first"
        )

    shutil.copytree(STATIC_DIR, out_dir, dirs_exist_ok=True)
    api_dir = out_dir / "api"
    api_dir.mkdir(exist_ok=True)
    for route, name in ROUTE_FILES.items():
        shutil.copyfile(data_dir / name, api_dir / route)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default="published/dashboard", help="exported JSON dir")
    parser.add_argument("--out", default="_site", help="output dir for the static site")
    args = parser.parse_args()
    build_site(args.data, args.out)
    print(f"Built static dashboard from {args.data} into {args.out}")


if __name__ == "__main__":
    main()
