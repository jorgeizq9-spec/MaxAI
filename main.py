import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"JARVIS Bot Running")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

# Iniciar servidor en segundo plano para engañar a Render
threading.Thread(target=run_health_check_server, daemon=True).start()
import os
import json
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from supabase import create_client, Client
import google.generativeai as genai

# Configuración de logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# 1. Cargar Variables de Entorno
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# 2. Inicializar Clientes
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# 3. Funciones de Base de Datos para JARVIS (Tool Calling)
def crear_tarea(nombre_tarea: str, prioridad: str = "Media", fecha_entrega: str = None) -> str:
    """Crea una nueva tarea en la base de datos."""
    data = {"nombre_tarea": nombre_tarea, "prioridad": prioridad}
    if fecha_entrega:
        data["fecha_entrega"] = fecha_entrega
    res = supabase.table("tareas").insert(data).execute()
    return f"Tarea creada exitosamente: {res.data}"

def listar_tareas_pendientes() -> str:
    """Obtiene las tareas que no están completadas."""
    res = supabase.table("tareas").select("*").neq("progreso", "Completada").execute()
    return json.dumps(res.data, ensure_ascii=False)

def crear_evento(titulo: str, fecha_inicio: str, ubicacion: str = None) -> str:
    """Registra un evento o compromiso en la agenda."""
    data = {"titulo": titulo, "fecha_inicio": fecha_inicio}
    if ubicacion:
        data["ubicacion"] = ubicacion
    res = supabase.table("eventos").insert(data).execute()
    return f"Evento agendado exitosamente: {res.data}"

def listar_eventos() -> str:
    """Muestra los eventos programados en la agenda."""
    res = supabase.table("eventos").select("*").execute()
    return json.dumps(res.data, ensure_ascii=False)

def crear_nota(titulo: str, contenido: str, categoria: str = "General", tags: str = "") -> str:
    """Guarda una nota de conocimiento, apuntes o comandos."""
    data = {"titulo": titulo, "contenido": contenido, "categoria": categoria, "tags": tags}
    res = supabase.table("notas_conocimiento").insert(data).execute()
    return f"Nota guardada exitosamente: {res.data}"

def buscar_notas(categoria: str = None) -> str:
    """Busca notas de conocimiento guardadas."""
    query = supabase.table("notas_conocimiento").select("*")
    if categoria:
        query = query.ilike("categoria", f"%{categoria}%")
    res = query.execute()
    return json.dumps(res.data, ensure_ascii=False)

# Mapeo de herramientas para Gemini
herramientas = [
    crear_tarea, listar_tareas_pendientes, 
    crear_evento, listar_eventos, 
    crear_nota, buscar_notas
]

# Configuración del modelo Gemini
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    tools=herramientas,
    system_instruction=(
        "Eres JARVIS, un asistente personal inteligente y eficiente. "
        "Tienes acceso a la base de datos del usuario mediante herramientas. "
        "Cuando el usuario te pida guardar, consultar o gestionar tareas, eventos o notas, "
        "utiliza las herramientas disponibles y responde siempre con un tono cercano, claro y profesional."
    )
)

# 4. Manejador de mensajes de Telegram
async def atender_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_usuario = update.message.text
    chat = model.start_chat(enable_automatic_function_calling=True)

    try:
        response = await chat.send_message_async(texto_usuario)
        await update.message.reply_text(response.text)
    except Exception as e:
        print(f"❌ ERROR DETALLADO EN GEMINI/SUPABASE: {e}")
        logging.error(f"Error al procesar mensaje: {e}")
        await update.message.reply_text("Lo siento, ha ocurrido un error procesando tu solicitud.")

# 5. Punto de entrada principal
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, atender_mensaje))
    print("🤖 JARVIS está activo y escuchando en Telegram...")
    app.run_polling()
