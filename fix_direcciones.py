from pathlib import Path

files = list(Path("templates").rglob("*.html"))

replacements = [
    ("Diez de Julio 354, Santiago", "Diez de Julio 354, Macul, Región Metropolitana"),
    ("Diez de Julio 354,\nSantiago", "Diez de Julio 354, Macul, Región Metropolitana"),
    ("Diez de Julio 354,\r\nSantiago", "Diez de Julio 354, Macul, Región Metropolitana"),
    ("Diez%20de%20Julio%20354%2C%20Santiago%2C%20Chile", "Diez%20de%20Julio%20354%2C%20Macul%2C%20Chile"),
    ('"addressLocality": "Santiago"', '"addressLocality": "Macul"'),
]

for p in files:
    text = p.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        text = text.replace(old, new)
    if text != original:
        p.write_text(text, encoding="utf-8")
        print("UPDATED:", p)
