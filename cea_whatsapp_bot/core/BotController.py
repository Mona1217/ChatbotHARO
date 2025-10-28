# BotController.py
from AuthClient import AuthClient

# memoria simple por número de WhatsApp
session_state = {}
# session_state[numero] = { "step": "ASK_EMAIL" | "WAITING_OTP", "email": "..." }

class BotController:

    @staticmethod
    def procesar_mensaje(numero_whatsapp: str, texto_usuario: str) -> str:
        estado = session_state.get(numero_whatsapp)

        # Estado inicial: pedir correo
        if estado is None or estado["step"] == "ASK_EMAIL":
            email = texto_usuario.strip()

            # validación simple
            if "@" not in email or "." not in email:
                # aún no es correo válido → pídeselo
                session_state[numero_whatsapp] = { "step": "ASK_EMAIL", "email": None }
                return "📩 Dame tu correo registrado (ej: nombre@correo.com):"

            # ya parece correo → guardo
            session_state[numero_whatsapp] = { "step": "WAITING_OTP", "email": email }

            # llamo al backend Java para que mande el correo de verificación
            enviado = AuthClient.enviar_codigo(email)

            if enviado:
                return (
                    f"✅ Listo. Envié un código de verificación a {email}.\n"
                    "✍️ Respóndeme aquí con ese código de 6 dígitos."
                )
            else:
                # si el back falló
                session_state[numero_whatsapp] = { "step": "ASK_EMAIL", "email": None }
                return "❌ No pude enviar el código. Verifica que el correo exista en el sistema."

        # Si ya estamos esperando OTP
        if estado["step"] == "WAITING_OTP":
            otp = texto_usuario.strip()
            email = estado["email"]
            # AQUI luego harás la validación del OTP contra el backend.
            # Por ahora solo confirmas recepción.
            return f"📬 Recibí tu código {otp} para {email}. (Validación viene después)"

        # Fallback
        session_state[numero_whatsapp] = { "step": "ASK_EMAIL", "email": None }
        return "📩 Dame tu correo registrado:"
