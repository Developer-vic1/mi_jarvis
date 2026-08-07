"""
config.py — Configuración centralizada de Jarvis.

Todas las rutas, constantes y parámetros ajustables en un único lugar.
Modificar aquí afecta a todo el sistema sin tocar otros módulos.
"""

import os

# ─────────────────────────────────────────────────────────────────────────────
# RUTAS BASE
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATOS_DIR = os.path.join(BASE_DIR, "datos")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
MODELOS_VOZ_DIR = os.path.join(BASE_DIR, "modelos_voz")

# ─────────────────────────────────────────────────────────────────────────────
# VOZ / TTS
# ─────────────────────────────────────────────────────────────────────────────
MODELO_VOZ = os.path.join(MODELOS_VOZ_DIR, "es_ES-davefx-medium.onnx")
SAMPLE_RATE_VOZ = 22050          # Hz del modelo Piper es_ES-davefx-medium

# ─────────────────────────────────────────────────────────────────────────────
# RECONOCIMIENTO DE VOZ
# ─────────────────────────────────────────────────────────────────────────────
IDIOMA_STR = "es-ES"
TIMEOUT_ESCUCHA = 5              # segundos esperando que el usuario hable
PHRASE_TIME_LIMIT = 12           # segundos máximos de una frase
AJUSTE_RUIDO_DURATION = 0.5      # segundos para calibrar ruido (mejorado de 1s)

# ─────────────────────────────────────────────────────────────────────────────
# SESIÓN CONVERSACIONAL
# ─────────────────────────────────────────────────────────────────────────────
TIMEOUT_SESION = 30              # segundos de inactividad antes de volver a reposo
WAKE_WORDS = ["jarvis", "oye jarvis", "hey jarvis", "eh jarvis"]
SLEEP_WORDS = ["descansa", "hasta luego", "bye", "adiós", "apagar sistema",
               "desconectar", "salir", "apágate"]

# ─────────────────────────────────────────────────────────────────────────────
# NLP
# ─────────────────────────────────────────────────────────────────────────────
UMBRAL_FUZZY = 72                # score mínimo de rapidfuzz para aceptar coincidencia
UMBRAL_INTENCION = 65            # score mínimo para aceptar intención

# ─────────────────────────────────────────────────────────────────────────────
# APLICACIONES
# ─────────────────────────────────────────────────────────────────────────────
APPS_INDEX_PATH = os.path.join(DATOS_DIR, "apps_index.json")
APPS_INDEX_MAX_AGE_HOURS = 24    # regenerar índice si tiene más de N horas
APPS_DESKTOP_DIRS = [
    "/usr/share/applications/",
    os.path.expanduser("~/.local/share/applications/"),
]

# ─────────────────────────────────────────────────────────────────────────────
# MEMORIA / BASE DE DATOS
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(DATOS_DIR, "jarvis.db")
ALIAS_PATH = os.path.join(DATOS_DIR, "alias.json")
HISTORIAL_MAX_ROWS = 1000        # filas máximas en tabla historial antes de rotar

# ─────────────────────────────────────────────────────────────────────────────
# LOGS
# ─────────────────────────────────────────────────────────────────────────────
LOG_PATH = os.path.join(LOGS_DIR, "jarvis.log")
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB por archivo de log
LOG_BACKUP_COUNT = 3             # número de archivos de respaldo

# ─────────────────────────────────────────────────────────────────────────────
# DESARROLLO / PROYECTOS
# ─────────────────────────────────────────────────────────────────────────────
HOME_DIR = os.path.expanduser("~")
CARPETAS_CONOCIDAS: dict[str, str] = {
    "descargas": os.path.join(HOME_DIR, "Downloads"),
    "documentos": os.path.join(HOME_DIR, "Documents"),
    "escritorio": os.path.join(HOME_DIR, "Desktop"),
    "desktop": os.path.join(HOME_DIR, "Desktop"),
    "imágenes": os.path.join(HOME_DIR, "Pictures"),
    "imagenes": os.path.join(HOME_DIR, "Pictures"),
    "videos": os.path.join(HOME_DIR, "Videos"),
    "música": os.path.join(HOME_DIR, "Music"),
    "musica": os.path.join(HOME_DIR, "Music"),
    "inicio": HOME_DIR,
    "home": HOME_DIR,
    "jarvis": os.path.join(HOME_DIR, "mi_jarvis"),
    "mi_jarvis": os.path.join(HOME_DIR, "mi_jarvis"),
}

CARPETA_OPERACIONES_DEFAULT = HOME_DIR   # Jarvis preguntará si no se especifica

# ─────────────────────────────────────────────────────────────────────────────
# WEB
# ─────────────────────────────────────────────────────────────────────────────
NAVEGADOR_CMD = "xdg-open"
SITIOS_CONOCIDOS: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "google": "https://www.google.com",
    "openai": "https://openai.com",
    "chatgpt": "https://chat.openai.com",
    "laravel": "https://laravel.com/docs",
    "python": "https://docs.python.org/3/",
    "documentación de python": "https://docs.python.org/3/",
    "ubuntu": "https://ubuntu.com",
    "docker": "https://docs.docker.com",
    "flutter": "https://flutter.dev/docs",
    "linkedin": "https://www.linkedin.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "reddit": "https://www.reddit.com",
    "npm": "https://www.npmjs.com",
    "pypi": "https://pypi.org",
    "gitlab": "https://gitlab.com",
    "whatsapp": "https://web.whatsapp.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://www.netflix.com",
}

# ─────────────────────────────────────────────────────────────────────────────
# MODO DEBUG
# ─────────────────────────────────────────────────────────────────────────────
MODO_DEBUG = os.getenv("JARVIS_DEBUG", "0") == "1"
