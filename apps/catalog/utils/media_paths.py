"""
Utilidades para rutas de medios del catálogo.
Estructura objetivo: media/products/<sku>/main.webp, 01.webp, 02.webp, banner.webp (opcional).
"""
import re
import unicodedata


def sanitize_filename(filename: str) -> str:
    """
    Sanitiza un nombre de archivo: quita espacios, comas, acentos,
    caracteres raros, pasa a minúsculas, reemplaza por guiones/underscore.
    """
    if not filename or not isinstance(filename, str):
        return "image"
    # Normalizar unicode (NFD) y quitar acentos
    n = unicodedata.normalize("NFD", filename)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    # Solo alfanuméricos, guión, punto, underscore
    n = re.sub(r"[^\w\s.\-]", "", n, flags=re.IGNORECASE)
    n = re.sub(r"[\s,]+", "_", n)
    n = n.strip("._-").lower()
    if not n:
        return "image"
    # Evitar múltiples guiones bajos
    n = re.sub(r"_+", "_", n)
    return n[:200]  # límite razonable


def product_image_upload_to(instance, filename: str) -> str:
    """
    upload_to dinámico para ProductImage.
    Guarda en: products/<sku>/<sanitized_filename>.
    Requiere que instance tenga product con sku (puede no estar guardado aún).
    """
    sku = "unknown"
    if instance and getattr(instance, "product", None):
        product = instance.product
        if getattr(product, "sku", None):
            sku = product.sku.strip() or "unknown"
    # Sanitizar SKU para path (sin espacios ni caracteres problemáticos)
    sku_clean = re.sub(r"[^\w\-]", "", sku, flags=re.IGNORECASE).strip() or "unknown"
    base = sanitize_filename(filename)
    if not base.endswith((".webp", ".png", ".jpg", ".jpeg", ".gif")):
        base = f"{base}.webp"
    return f"products/{sku_clean}/{base}"
