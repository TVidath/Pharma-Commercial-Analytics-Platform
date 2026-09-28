import os
from pathlib import Path
import json

root = Path(r"c:\b\pharma-commercial-analytics-main")
old_name = "Project Catalyst"
new_name = "Pharma Commercial Analytics Platform"
old_name_upper = "PROJECT CATALYST"
new_name_upper = "PHARMA COMMERCIAL ANALYTICS PLATFORM"

for p in root.rglob("*"):
    if p.is_file() and not ".git" in p.parts and not "__pycache__" in p.parts and not ".venv" in p.parts and p.suffix in [".sql", ".sh", ".ipynb", "", ".yml", ".yaml", ".txt"]:
        try:
            content = p.read_text(encoding="utf-8")
            changed = False
            
            if old_name in content:
                content = content.replace(old_name, new_name)
                changed = True
            if old_name_upper in content:
                content = content.replace(old_name_upper, new_name_upper)
                changed = True
                
            if changed:
                p.write_text(content, encoding="utf-8")
                print(f"Updated {p}")
        except Exception:
            pass
