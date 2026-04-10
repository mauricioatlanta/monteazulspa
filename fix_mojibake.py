from pathlib import Path

def fix_mojibake(text):
    try:
        for _ in range(3):
            text = text.encode('latin1').decode('utf-8')
    except:
        pass
    return text

files = [
    "templates/core/home_welcome.html",
    "templates/base.html",
]

for f in files:
    p = Path(f)
    raw = p.read_text(encoding="utf-8", errors="ignore")
    fixed = fix_mojibake(raw)
    p.write_text(fixed, encoding="utf-8")
    print("FIXED:", f)
