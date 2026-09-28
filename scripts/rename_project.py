import os
from pathlib import Path

root = Path(r"c:\b\pharma-commercial-analytics-main")
old_name = "Pharma Commercial Analytics Platform"
new_name = "Pharma Commercial Analytics Platform"

for p in root.rglob("*"):
    if p.is_file() and not ".git" in p.parts and not "__pycache__" in p.parts and p.suffix in [".py", ".md", ".txt"]:
        try:
            content = p.read_text(encoding="utf-8")
            if old_name in content:
                content = content.replace(old_name, new_name)
                p.write_text(content, encoding="utf-8")
                print(f"Updated {p}")
        except Exception:
            pass
