# core/menu.py
from typing import Tuple, Dict

class MenuHandler:
    """
    Flujo conversacional del chatbot:
      - "Soy nuevo" -> consentimiento -> registro (10 campos, SIN 'estado')
      - Se envía 'tipoEstudiante'='prospecto' (lo agrega la capa web).
      - Login con {login,password} (password en SHA-256).
      - Consulta estudiante por documento.
    """
    def __init__(self):
        self.menus: Dict[str, Dict] = {
            "inicio": {
                "mensaje":
                    "👋 *Academia de Conducción HARO*\n\n"
                    "Elige una opción (pulsa un botón o escribe el número):\n"
                    "1️⃣ *Soy nuevo* (información / matrícula)\n"
                    "2️⃣ *Soy estudiante activo*\n"
                    "3️⃣ *Registrarme (prospecto)*\n"
                    "4️⃣ *Iniciar sesión*",
                "transiciones": {"1": "consent_nuevo", "2": "consulta_estudiante", "3": "reg_intro", "4": "login_intro"}
            },

            "consent_nuevo": {
                "mensaje":
                    "🛡️ *Tratamiento de datos*\n"
                    "Autorizas el tratamiento de tus datos (Ley 1581 de 2012) para gestionar tu proceso?\n"
                    "Responde *acepto* o *no*.",
                "transiciones": {"acepto": "reg_intro", "no": "inicio", "*": "consent_nuevo"}
            },

            "consulta_estudiante": {
                "mensaje":
                    "✍️ Escribe tu número de cédula para verificar tu registro.\n"
                    "Ejemplo: 123456789\n"
                    "(Se consulta en /api/estudiantes/por-documento/{numeroDocumento})",
                "transiciones": {"volver": "inicio", "*": "consulta_estudiante"}
            },

            "login_intro": {
                "mensaje":
                    "🔐 *Iniciar sesión*\n"
                    "Escribe tu *usuario* (ej.: ayuda69).",
                "transiciones": {"volver": "inicio", "*": "login_user"}
            },
            "login_user": {
                "mensaje": "🧑 Ingresa tu *usuario* (ej.: ayuda69).",
                "transiciones": {"volver": "inicio", "*": "login_pass"}
            },
            "login_pass": {
                "mensaje": "🔑 Ingresa tu *contraseña* (ej.: ayuda123).",
                "transiciones": {"volver": "inicio", "*": "login_enviando"}
            },
            "login_enviando": {"mensaje": "⏳ Validando credenciales…", "transiciones": {"*": "login_enviando"}},

            # Registro prospecto (10 campos; SIN pedir 'estado')
            "reg_intro": {
                "mensaje":
                    "📝 *Registro de matrícula (prospecto)*\n"
                    "Datos requeridos (con ejemplo):\n"
                    "1) nombre (ej.: Daniela)\n"
                    "2) apellido (ej.: Piñeros)\n"
                    "3) tipoDocumento (ej.: CC | TI | CE | Pasaporte)\n"
                    "4) numeroDocumento (ej.: 123456789)\n"
                    "5) categoria (ej.: A2 | B1 | C1)\n"
                    "6) telefono (ej.: 3001234567)\n"
                    "7) email (ej.: usuario@dominio.com)\n"
                    "8) direccion (ej.: Calle 123 #45-67, Bogotá)\n"
                    "9) usuario (ej.: daniela.pineros)\n"
                    "10) contrasena (ej.: Secreta*2025)\n\n"
                    "(Se enviará *tipoEstudiante='prospecto'* automáticamente)\n"
                    "Escribe *empezar* para continuar.",
                "transiciones": {"empezar": "reg_nombre", "volver": "inicio", "*": "reg_intro"}
            },
            "reg_nombre":          {"mensaje": "1/10) *nombre* (ej.: Daniela)",                           "transiciones": {"*": "reg_apellido",        "volver": "inicio"}},
            "reg_apellido":        {"mensaje": "2/10) *apellido* (ej.: Piñeros)",                         "transiciones": {"*": "reg_tipoDocumento",   "volver": "inicio"}},
            "reg_tipoDocumento":   {"mensaje": "3/10) *tipoDocumento* (ej.: CC | TI | CE | Pasaporte)",   "transiciones": {"*": "reg_numeroDocumento", "volver": "inicio"}},
            "reg_numeroDocumento": {"mensaje": "4/10) *numeroDocumento* (ej.: 123456789)",                "transiciones": {"*": "reg_categoria",       "volver": "inicio"}},
            "reg_categoria":       {"mensaje": "5/10) *categoria* (ej.: A2 | B1 | C1)",                   "transiciones": {"*": "reg_telefono",        "volver": "inicio"}},
            "reg_telefono":        {"mensaje": "6/10) *telefono* (ej.: 3001234567)",                      "transiciones": {"*": "reg_email",           "volver": "inicio"}},
            "reg_email":           {"mensaje": "7/10) *email* (ej.: usuario@dominio.com)",                "transiciones": {"*": "reg_direccion",       "volver": "inicio"}},
            "reg_direccion":       {"mensaje": "8/10) *direccion* (ej.: Calle 123 #45-67, Bogotá)",       "transiciones": {"*": "reg_usuario",         "volver": "inicio"}},
            "reg_usuario":         {"mensaje": "9/10) *usuario* (ej.: daniela.pineros)",                  "transiciones": {"*": "reg_contrasena",      "volver": "inicio"}},
            "reg_contrasena":      {"mensaje": "10/10) *contrasena* (ej.: Secreta*2025)",                 "transiciones": {"*": "reg_resumen",         "volver": "inicio"}},
            "reg_resumen": {
                "mensaje": "📦 Verás una vista previa organizada. Escribe *enviar* para registrar o *volver* para cancelar.",
                "transiciones": {"enviar": "reg_enviando", "volver": "inicio", "*": "reg_resumen"}
            },
            "reg_enviando": {"mensaje": "⏳ Registrando prospecto…", "transiciones": {"*": "reg_enviando"}},
        }

    def siguiente(self, estado: str, entrada: str) -> Tuple[str, str]:
        estado = (estado or "inicio")
        entrada_normalizada = (entrada or "").strip().lower()

        menu = self.menus.get(estado, self.menus["inicio"])
        trans = menu.get("transiciones", {})

        if entrada_normalizada in trans:
            nuevo = trans[entrada_normalizada]
        elif "*" in trans:
            nuevo = trans["*"]
        else:
            nuevo = estado

        if nuevo not in self.menus:
            return ("", nuevo)

        respuesta = self.menus[nuevo]["mensaje"]

        if entrada_normalizada not in trans and "*" not in trans:
            respuesta = f"⚠️ Opción no válida.\n\n{respuesta}"

        return respuesta, nuevo
