from core.menuHandler import MenuHandler

class ChatBotCore:
    """
    Clase principal del chatbot de la academia de conducción.
    Controla el flujo de conversación, llama al manejador de menús
    y genera las respuestas correspondientes.
    """

    def __init__(self):
        self.menu = MenuHandler()
        self.user_sessions = {}  # Guarda el estado actual de cada usuario

    def recibir_mensaje(self, user_id: str, mensaje: str) -> str:
        """
        Recibe un mensaje del usuario, lo procesa y devuelve la respuesta correspondiente.
        """
        # Normalizamos el texto
        mensaje = mensaje.strip().lower()

        # Si el usuario no tiene estado, inicia desde el menú principal
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = "inicio"

        estado_actual = self.user_sessions[user_id]
        respuesta, nuevo_estado = self.menu.procesar_opcion(estado_actual, mensaje)

        # Actualizar estado del usuario
        self.user_sessions[user_id] = nuevo_estado

        return respuesta
