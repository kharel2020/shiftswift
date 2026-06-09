#!/usr/bin/env python3
"""Build CloudPanel upload zips for Hostinger deployment."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deploy" / "cloudpanel" / "dist"
STAGE = ROOT / ".pack-staging"

API_FILES = {
    "backend_stub": ROOT / "backend_stub",
    "migrations": ROOT / "migrations",
}
API_SCRIPTS = [
    "run_migrations.sh",
    "seed_app_users.py",
    "seed_billing_catalog.py",
    "seed_contract_templates.py",
    "seed_tenant_branding.py",
    "seed_hr_templates.py",
    "seed_time_punch.py",
]
EXCLUDE_DIRS = {".venv", "__pycache__", "uploads", ".git", ".pytest_cache"}
EXCLUDE_FILES = {".env", ".DS_Store"}


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for path in src.rglob("*"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDE_FILES:
            continue
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        if "storage" in rel.parts and "contracts" in rel.parts:
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def zip_dir(source: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(source).as_posix())


def main() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    OUT.mkdir(parents=True, exist_ok=True)

    api_root = STAGE / "api"
    api_root.mkdir(parents=True)
    copy_tree(ROOT / "backend_stub", api_root / "backend_stub")
    copy_tree(ROOT / "migrations", api_root / "migrations")
    (api_root / "scripts").mkdir(parents=True, exist_ok=True)
    for name in API_SCRIPTS:
        shutil.copy2(ROOT / "scripts" / name, api_root / "scripts" / name)
    shutil.copy2(ROOT / "deploy/cloudpanel/install-api.sh", api_root / "install-api.sh")
    shutil.copy2(ROOT / "deploy/cloudpanel/INSTALL-API.md", api_root / "INSTALL-API.md")
    example = ROOT / "backend_stub/.env.production.example"
    if example.exists():
        shutil.copy2(example, api_root / "backend_stub/.env.production.example")

    front_root = STAGE / "frontend"
    copy_tree(ROOT / "frontend", front_root)
    shutil.copy2(ROOT / "deploy/cloudpanel/INSTALL-FRONTEND.md", front_root / "INSTALL-FRONTEND.md")

    api_zip = OUT / "shiftswifthr-api.zip"
    front_zip = OUT / "shiftswifthr-frontend.zip"
    zip_dir(api_root, api_zip)
    zip_dir(front_root, front_zip)
    shutil.rmtree(STAGE)

    print("Built:")
    for z in (api_zip, front_zip):
        size_kb = z.stat().st_size // 1024
        print(f"  {z}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
