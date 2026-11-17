"""Build the Conflict Watch website + console and publish it into the Streamlit app.

    python scripts/export_web.py     # 1. frozen numbers -> web/public/data (asserts)
    python scripts/build_site.py     # 2. npm build -> app/static/site/ (PWA) + app/static/conflictwatch.html (single file)
"""
import shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
if not (WEB / "node_modules").exists():
    subprocess.run(["npm", "ci"], cwd=WEB, check=True)
subprocess.run(["npm", "run", "build"], cwd=WEB, check=True)
out = ROOT / "app" / "static"
out.mkdir(parents=True, exist_ok=True)
shutil.rmtree(out / "site", ignore_errors=True)
shutil.copytree(WEB / "dist", out / "site")
shutil.copy(WEB / "dist-single" / "index.html", out / "conflictwatch.html")
shutil.copy(WEB / "dist-single" / "index.html", ROOT / "deck" / "conflictwatch.html")  # USB / offline backup
print("site ->", out / "site", "| single file ->", out / "conflictwatch.html")
