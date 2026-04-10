from pathlib import Path

from django.conf import settings


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def _extract_sku(product):
    if isinstance(product, dict):
        return (product.get("sku") or "").strip()
    return (getattr(product, "sku", "") or "").strip()


def _resolve_image_folder(base_dir, sku):
    folder = base_dir / sku
    if folder.exists() and folder.is_dir():
        return folder

    sku_lower = sku.lower()
    for child in base_dir.iterdir():
        if child.is_dir() and child.name.lower() == sku_lower:
            return child
    return None


def get_product_image_url(product):
    sku = _extract_sku(product)
    if not sku:
        return "/media/logomonteazul.png"

    images_root = Path(settings.BASE_DIR) / "imagenes"
    if not images_root.exists():
        return "/media/logomonteazul.png"

    folder = _resolve_image_folder(images_root, sku)
    if folder:
        files = sorted(
            f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        )
        if files:
            return f"/imagenes/{folder.name}/{files[0].name}"

    return "/media/logomonteazul.png"
