# Checklist de datos de WhatsApp API que necesito

Comparte estos datos (puedes ocultar partes sensibles si quieres):

1. Proveedor de API:
- Confirmame si usaremos `WhatsApp Cloud API de Meta` (recomendado).

2. Credenciales minimas:
- `WHATSAPP_ACCESS_TOKEN` (token permanente del System User).
- `WHATSAPP_PHONE_NUMBER_ID`.
- `WHATSAPP_VERIFY_TOKEN` (texto libre que defines tu).
- `WHATSAPP_API_VERSION` (si no, dejamos `v23.0`).

3. Configuracion de webhook:
- URL publica que vas a registrar en Meta (ejemplo: `https://tu-dominio.com/webhook`).
- Campo suscrito: `messages`.

4. Datos opcionales para produccion:
- `WABA_ID` (WhatsApp Business Account ID).
- `APP_ID`.
- `APP_SECRET`.
- Numero de WhatsApp de prueba o produccion (con codigo de pais).

5. Confirmaciones funcionales:
- Texto exacto del flujo que quieres en cada paso.
- Si quieres guardar las respuestas en DB (si/no y cual DB).
