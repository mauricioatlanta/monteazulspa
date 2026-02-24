"""One-off: list normalized SKUs for cataliticos-twc."""
import os
import sys
import re
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.catalog.models import Product, Category

root = Category.objects.filter(slug="cataliticos-twc").first()
if not root:
    print("Category cataliticos-twc not found")
    sys.exit(1)

skus = list(Product.objects.filter(category=root).values_list("sku", flat=True))


def norm(s):
    s = (s or "").upper().strip().replace("_", "-").replace("--", "-").replace(",", ".").replace(" ", "")
    m = re.match(r"^(TWCAT)0+([0-9]+)(.*)$", s)
    if m:
        s = f"{m.group(1)}{int(m.group(2))}{m.group(3)}"
    return s


dbn = [(s, norm(s)) for s in skus]
print("DB normalized:")
for s, n in dbn:
    print(s, "=>", n)
