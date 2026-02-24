# Webpay Plus (Transbank) - Configuración

## 1. Instalar dependencia

```bash
pip install transbank-sdk
# o
pip install -r requirements-webpay.txt
```

## 2. Variables de entorno

En `.env` o variables del servidor (NUNCA hardcodear):

```env
TBK_ENV=integration
TBK_COMMERCE_CODE=597055555532
TBK_API_KEY=tu_api_key_secret
TBK_RETURN_URL=https://www.monteazulspa.cl/carrito/webpay/retorno/
```

- **integration** | **production**: Ambiente de Transbank.
- **TBK_COMMERCE_CODE**: En integración usa `597055555532`; en producción tus credenciales reales.
- **TBK_API_KEY**: API Key que Transbank entrega (headers `Tbk-Api-Key-Id` y `Tbk-Api-Key-Secret`).
- **TBK_RETURN_URL**: Debe ser URL pública HTTPS a donde Transbank redirige después del pago.

## 3. Flujo

1. Usuario en checkout_review → **Pagar con Webpay** → `webpay_start`
2. Se crea transacción con `tx.create()`, se guarda `token_ws` y se redirige (POST) a Webpay.
3. Usuario paga en Webpay y Transbank redirige (POST) a `TBK_RETURN_URL`.
4. `webpay_return` recibe `token_ws`, hace `tx.commit()`, guarda datos y llama a `payment_success` si aprobado.

## 4. Prueba en integración

- Usa `TBK_ENV=integration` con credenciales de prueba.
- `TBK_RETURN_URL` debe ser accesible desde internet (ngrok para local).
- Transbank recomienda `buy_order` único: el formato MAZ-000123 cumple.
