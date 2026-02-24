"""
Servicio Transbank Webpay Plus.
Configuración desde variables de entorno (TBK_ENV, TBK_COMMERCE_CODE, TBK_API_KEY).
"""

from django.conf import settings
from transbank.common.integration_type import IntegrationType
from transbank.common.options import WebpayOptions
from transbank.webpay.webpay_plus.transaction import Transaction


def webpay_tx() -> Transaction:
    env_val = getattr(settings, "TBK_ENV", "integration").strip().lower()
    commerce_code = getattr(settings, "TBK_COMMERCE_CODE", "").strip()
    api_key = getattr(settings, "TBK_API_KEY", "").strip()

    integration = (
        IntegrationType.TEST if env_val == "integration" else IntegrationType.LIVE
    )
    return Transaction(WebpayOptions(commerce_code, api_key, integration))
