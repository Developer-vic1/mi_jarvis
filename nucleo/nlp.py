"""
nucleo/nlp.py — Motor de Procesamiento de Lenguaje Natural de Jarvis.

Responsabilidades:
- Normalizar texto de entrada (sin tildes, lowercase, strip).
- Corregir errores fonéticos y tipográficos con rapidfuzz.
- Extraer intención del usuario a partir de un catálogo de sinónimos.
- Extraer entidades (nombre de app, URL, expresión, carpeta, etc.).
- No depender de cadenas exactas — usar coincidencia semántica aproximada.
"""

import re
import unicodedata
import logging
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz, process as rfprocess  # type: ignore[import]
from config import UMBRAL_FUZZY, UMBRAL_INTENCION

logger = logging.getLogger("jarvis.nlp")

# ─────────────────────────────────────────────────────────────────────────────
# CORRECCIONES FONÉTICAS COMUNES
# Palabras que suelen malescribirse o malescucharse. Se aplican antes del NLP.
# ─────────────────────────────────────────────────────────────────────────────
CORRECCIONES_FONETICAS: dict[str, str] = {
    # Aplicaciones
    "doker": "docker",
    "dóker": "docker",
    "cromo": "chrome",
    "crome": "chrome",
    "corome": "chrome",
    "goggle": "google",
    "gúgel": "google",
    "gugel": "google",
    "firefox": "firefox",
    "fáierfox": "firefox",
    "opéra": "opera",
    "picharm": "pycharm",
    "paicharm": "pycharm",
    "vscode": "visual studio code",
    "vs code": "visual studio code",
    "fluter": "flutter",
    "pladmin": "pgadmin",
    "postman": "postman",
    "tilic": "tilix",
    "tilinks": "tilix",
    "androi": "android",
    "obes": "obs",
    # Términos técnicos
    "gitpull": "git pull",
    "gitstatus": "git status",
    "guit": "git",
    "laravel": "laravel",
    "laraval": "laravel",
    "fluter": "flutter",
    "postgres": "postgresql",
    "postgre": "postgresql",
    "maicol": "mysql",
    "mayecel": "mysql",
    # Carpetas
    "descargas": "descargas",
    "descarga": "descargas",
    "documentos": "documentos",
    "escritoiro": "escritorio",
    # Comandos generales
    "ábrir": "abrir",
    "habre": "abre",
    "abrir": "abrir",
}

# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO DE INTENCIONES
# Para cada intención: lista de frases/palabras disparadoras.
# NLP busca la mejor coincidencia fuzzy contra estas frases.
# ─────────────────────────────────────────────────────────────────────────────
CATALOGO_INTENCIONES: dict[str, list[str]] = {
    # ── Aplicaciones ──────────────────────────────────────────────────────────
    "ABRIR_APP": [
        "abre", "abrir", "ejecuta", "ejecutar", "lanza", "lanzar",
        "inicia", "iniciar", "abre la aplicación", "abre el programa",
        "quiero abrir", "necesito abrir", "podrías abrir", "puedes abrir",
        "haz el favor de abrir", "abre por favor", "pon", "poner",
        "arranca", "arrancar", "activa", "activar",
    ],
    # ── Macro Integrador SAVP-TIS3 ─────────────────────────────────────────────
    "ABRIR_INTEGRADOR": [
        "abre mi integrador",
        "abrir integrador",
        "inicia mi integrador",
        "abre proyecto integrador",
        "abre el proyecto",
        "carga el proyecto",
        "abre entorno de trabajo",
        "carga entorno",
        "abre savp",
        "abre savp tis3",
        "inicia savp",
        "proyecto savp",
        "trabajo integrador",
        "quiero trabajar",
        "vamos a programar",
    ],


    # ── Búsqueda web ──────────────────────────────────────────────────────────
    "BUSCAR_WEB": [
        "busca", "buscar", "googlea", "googlear", "investiga", "investigar",
        "busca en google", "búscame", "quiero saber sobre", "información sobre",
        "qué es", "dime sobre", "busca información de",
    ],

    # ── Abrir sitio web conocido ──────────────────────────────────────────────
    # Frases específicas de sitios se evalúan ANTES que ABRIR_APP (más específico)
    "ABRIR_WEB": [
        "abre youtube", "ve a youtube", "ir a youtube",
        "abre gmail", "abre github", "abre spotify", "abre netflix",
        "abre whatsapp web", "abre twitter", "abre reddit", "abre openai",
        "abre chatgpt", "abre stackoverflow", "abre linkedin",
        "ir a", "navega a", "abre la pagina", "abre el sitio",
        "ve a", "entra a", "abre la web", "visita",
    ],

    # ── Hora / fecha ──────────────────────────────────────────────────────────
    "HORA": [
        "qué hora es", "hora", "qué hora", "dime la hora", "la hora",
        "me dices la hora", "qué horas son",
    ],
    "FECHA": [
        "qué fecha es", "fecha de hoy", "qué día es hoy", "la fecha",
        "qué día es", "cuál es la fecha", "día de hoy", "hoy es",
    ],
    "DIA_SEMANA": [
        "qué día de la semana", "día de la semana", "qué día es",
    ],
    "MES": ["qué mes es", "mes actual", "en qué mes estamos"],
    "AÑO": ["qué año es", "año actual", "en qué año estamos"],

    # ── Cálculos ──────────────────────────────────────────────────────────────
    "CALCULAR": [
        "cuánto es", "calcula", "cuánto son", "resultado de", "resuelve",
        "cuanto da", "opera", "cuánto vale", "dime el resultado",
        "cuánto es el resultado", "saca", "calcúlame",
    ],

    # ── Definiciones ──────────────────────────────────────────────────────────
    "DEFINIR": [
        "qué significa", "define", "qué es", "significado de", "definición de",
        "qué quiere decir", "qué significa la palabra", "explícame",
        "me puedes decir qué es",
    ],

    # ── CRUD archivos/carpetas ────────────────────────────────────────────────
    "ABRIR_CARPETA": [
        "abre la carpeta", "abre mi carpeta", "ve a descargas",
        "ve al escritorio", "abre documentos", "abre descargas",
        "abre el escritorio", "muéstrame la carpeta", "ir a la carpeta",
    ],
    "CREAR_CARPETA": [
        "crea una carpeta", "crea el directorio", "nueva carpeta",
        "crear carpeta", "hacer una carpeta", "crea la carpeta",
        "haz una carpeta llamada",
    ],
    "CREAR_ARCHIVO": [
        "crea un archivo", "nuevo archivo", "crear archivo",
        "haz un archivo", "crea el archivo", "genera un archivo",
    ],
    "RENOMBRAR": [
        "renombra", "renombrar", "cambia el nombre", "cambiar nombre",
        "llámalo", "ponle el nombre",
    ],
    "MOVER": [
        "mueve", "mover", "traslada", "trasladar", "lleva", "llevar",
        "pasa a", "pasar a",
    ],
    "COPIAR": [
        "copia", "copiar", "duplica", "duplicar", "haz una copia de",
    ],
    "ELIMINAR": [
        "elimina", "eliminar", "borra", "borrar", "bórralo", "bórrala",
        "quita", "quitar", "suprime", "suprimir", "borra el archivo",
        "borra la carpeta",
    ],
    "BUSCAR_ARCHIVO": [
        "busca el archivo", "encuentra el archivo", "dónde está",
        "busca la carpeta", "localiza",
    ],

    # ── Linux / sistema ───────────────────────────────────────────────────────
    "LINUX_APAGAR": [
        "apaga el sistema", "apaga la computadora", "apaga la pc",
        "apagar sistema", "apagar la máquina",
    ],
    "LINUX_REINICIAR": [
        "reinicia", "reiniciar", "reinicia el sistema", "reinicia la pc",
        "reiniciar el sistema",
    ],
    "LINUX_BLOQUEAR": [
        "bloquea la pantalla", "bloquear pantalla", "bloquea la sesión",
        "bloquear sesión", "cierra la pantalla",
    ],
    "LINUX_CERRAR_SESION": [
        "cierra sesión", "cerrar sesión", "salir de la sesión",
    ],
    "LINUX_VOL_UP": [
        "sube el volumen", "más volumen", "aumenta el volumen",
        "subir volumen", "sube el sonido",
    ],
    "LINUX_VOL_DOWN": [
        "baja el volumen", "menos volumen", "reduce el volumen",
        "bajar volumen", "baja el sonido",
    ],
    "LINUX_VOL_MUTE": ["silencio", "silenciar", "mute", "sin sonido"],
    "LINUX_BRILLO_UP": [
        "sube el brillo", "más brillo", "aumenta el brillo", "subir brillo",
    ],
    "LINUX_BRILLO_DOWN": [
        "baja el brillo", "menos brillo", "reduce el brillo", "bajar brillo",
    ],
    "LINUX_RAM": [
        "cuánta ram", "uso de memoria", "ram", "memoria ram", "memoria disponible",
        "cuánta memoria", "uso de ram",
    ],
    "LINUX_CPU": [
        "uso del cpu", "cpu", "uso del procesador", "procesador", "temperatura cpu",
        "carga del sistema",
    ],
    "LINUX_DISCO": [
        "espacio en disco", "disco duro", "almacenamiento", "espacio disponible",
        "cuánto disco", "espacio libre",
    ],
    "LINUX_PROCESOS": [
        "muéstrame los procesos", "procesos del sistema", "qué está corriendo",
        "ver procesos", "htop",
    ],
    "LINUX_ACTUALIZAR": [
        "actualiza el sistema", "actualizar ubuntu", "apt update",
        "instala actualizaciones", "actualizar paquetes",
    ],

    # ── Desarrollo ────────────────────────────────────────────────────────────
    "GIT_PULL": ["git pull", "haz git pull", "actualiza el repositorio"],
    "GIT_STATUS": ["git status", "estado del repositorio", "estado del git"],
    "GIT_LOG": ["git log", "ver commits", "historial de commits"],
    "GIT_PUSH": ["git push", "sube los cambios", "empuja los cambios"],
    "DOCKER_UP": [
        "levanta docker", "docker compose up", "sube los contenedores",
        "levanta los contenedores", "inicia docker compose",
    ],
    "DOCKER_DOWN": [
        "baja docker", "docker compose down", "detén los contenedores",
        "para los contenedores",
    ],
    "LARAVEL_SERVE": [
        "ejecuta laravel", "levanta laravel", "inicia laravel", "php artisan serve",
        "corre laravel",
    ],
    "FLUTTER_RUN": [
        "ejecuta flutter", "corre flutter", "flutter run", "inicia flutter",
    ],
    "PYTHON_RUN": [
        "ejecuta python", "corre el script", "ejecuta el script",
        "ejecuta el archivo python", "corre el archivo python",
    ],

    # ── Ventanas y Control del Escritorio ────────────────────────────────────
    "VENTANA_ACTIVA": [
        "en qué programa estoy", "en qué programa me encuentro",
        "en qué ventana estoy", "qué programa estoy usando",
        "qué ventana estoy usando", "dónde estoy",
        "cuál es la ventana activa", "qué programa tengo en pantalla",
        "en que programa estoy", "en que programa me encuentro",
        "en que ventana estoy", "que programa estoy usando",
        "que ventana estoy usando", "donde estoy",
        "cual es la ventana activa", "que programa tengo en pantalla",
    ],
    "LISTAR_APLICACIONES": [
        "qué aplicaciones tengo abiertas", "qué ventanas tengo abiertas",
        "cuáles ventanas están abiertas", "lista de aplicaciones abiertas",
        "mostrar ventanas abiertas", "qué programas están abiertos",
        "que aplicaciones tengo abiertas", "que ventanas tengo abiertas",
        "cuales ventanas estan abiertas", "lista de aplicaciones abiertas",
        "mostrar ventanas abiertas", "que programas estan abiertos",
    ],
    "CERRAR_APP": [
        "cierra", "cerrar", "cierra chrome", "cierra vscode",
        "cierra discord", "cierra la aplicación", "cierra el programa",
        "cierra la ventana", "cierra todas las terminales", "cierra las terminales",
        "cerrar aplicacion", "cerrar programa",
    ],
    "ENFOCAR_APP": [
        "cambiar a", "enfocar", "cambia a", "pon en primer plano",
        "muéstrame", "trae", "trae a primer plano", "trae al frente",
        "trae docker al frente", "trae chrome al frente", "trae vscode al frente",
        "enfoca chrome", "enfoca vscode", "enfoca docker",
    ],
    "MINIMIZAR_APP": [
        "minimiza", "minimizar", "minimiza chrome", "minimizar vscode",
        "minimiza la ventana", "minimiza el programa",
    ],
    "MAXIMIZAR_APP": [
        "maximiza", "maximizar", "maximiza vscode", "maximizar chrome",
        "maximiza la ventana", "maximiza el programa",
    ],
    "CAMBIAR_VENTANA": [
        "cambiar a", "enfocar", "cambia a", "pon en primer plano",
        "muéstrame", "trae",
    ],

    # ── Ayuda ─────────────────────────────────────────────────────────────────
    "AYUDA": [
        "qué puedes hacer", "ayuda", "comandos", "help", "qué sabes hacer",
        "cuáles son tus comandos", "qué funciones tienes", "lista de comandos",
        "en qué me puedes ayudar",
    ],

    # ── Alias ─────────────────────────────────────────────────────────────────
    "CREAR_ALIAS": [
        "crea un alias", "registra un alias", "cuando diga",
        "asigna el nombre", "ponle el alias",
    ],

    # ── Descanso ─────────────────────────────────────────────────────────────
    "DESCANSAR": [
        "descansa", "hasta luego", "bye", "adiós", "adios", "apagar sistema",
        "desconectar", "salir", "apágate", "modo reposo", "hasta pronto",
    ],
}

# Índice invertido: frase → intención (para búsqueda O(1) en casos exactos)
_INDICE_EXACTO: dict[str, str] = {
    frase: intencion
    for intencion, frases in CATALOGO_INTENCIONES.items()
    for frase in frases
}

# Lista plana de todas las frases disparadoras (para búsqueda fuzzy)
_TODAS_LAS_FRASES: list[str] = list(_INDICE_EXACTO.keys())


# ─────────────────────────────────────────────────────────────────────────────
# DATACLASS RESULTADO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResultadoNLP:
    """Resultado del análisis NLP de una frase del usuario."""
    texto_original: str
    texto_normalizado: str
    intencion: Optional[str] = None
    confianza: float = 0.0
    entidades: dict = field(default_factory=dict)

    @property
    def tiene_intencion(self) -> bool:
        return self.intencion is not None and self.confianza >= UMBRAL_INTENCION


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES PRINCIPALES
# ─────────────────────────────────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    """
    Normaliza texto: minúsculas, quitar tildes, eliminar caracteres especiales.

    Args:
        texto: Texto crudo del usuario.

    Returns:
        Texto normalizado.
    """
    texto = texto.lower().strip()
    # Quitar tildes sin eliminar ñ (la ñ no tiene equivalente en ASCII)
    resultado = []
    for char in texto:
        nfc = unicodedata.normalize("NFD", char)
        if unicodedata.category(nfc[0]) == "Ll" and len(nfc) > 1:
            # Es una letra con diacrítico (ej. á → a, é → e, pero ñ sigue siendo ñ)
            if nfc[0] == "n" and "\u0303" in nfc:
                resultado.append("ñ")
            else:
                resultado.append(nfc[0])
        else:
            resultado.append(char)
    texto = "".join(resultado)
    # Eliminar puntuación excepto letras, números, espacios y ñ
    texto = re.sub(r"[^\w\s\u00f1]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def corregir_fonetico(texto: str) -> str:
    """
    Aplica correcciones fonéticas al texto normalizado.
    También hace fuzzy matching contra el diccionario de correcciones.

    Args:
        texto: Texto ya normalizado.

    Returns:
        Texto con correcciones aplicadas.
    """
    palabras = texto.split()
    resultado = []

    for palabra in palabras:
        # Corrección exacta
        if palabra in CORRECCIONES_FONETICAS:
            resultado.append(CORRECCIONES_FONETICAS[palabra])
            continue

        # Corrección fuzzy
        match = rfprocess.extractOne(
            palabra,
            list(CORRECCIONES_FONETICAS.keys()),
            scorer=fuzz.ratio,
            score_cutoff=UMBRAL_FUZZY,
        )
        if match:
            resultado.append(CORRECCIONES_FONETICAS[match[0]])
            logger.debug("Corrección fonética: '%s' → '%s'", palabra, match[0])
        else:
            resultado.append(palabra)

    return " ".join(resultado)


# ─────────────────────────────────────────────────────────────────────────────
# NIVELES DE PRIORIDAD DEL NLP (1 a 5)
# 1. Macros
# 2. Intenciones Especiales
# 3. Aplicaciones (ABRIR_APP)
# 4. Preguntas
# 5. Conversación
# ─────────────────────────────────────────────────────────────────────────────
NIVELES_PRIORIDAD: list[list[str]] = [
    # Nivel 1: Macros (Máxima prioridad absoluta)
    [
        "ABRIR_INTEGRADOR",
        "MACRO_FLUTTER",
        "MACRO_PYTHON",
        "MACRO_LARAVEL",
    ],
    # Nivel 2: Intenciones Especiales, Ventanas y Comandos Específicos
    [
        "VENTANA_ACTIVA", "LISTAR_APLICACIONES", "CERRAR_APP", "ENFOCAR_APP",
        "MINIMIZAR_APP", "MAXIMIZAR_APP", "CAMBIAR_VENTANA", "AYUDA",
        "ABRIR_WEB", "ABRIR_CARPETA", "CREAR_CARPETA", "CREAR_ARCHIVO",
        "RENOMBRAR", "MOVER", "COPIAR", "ELIMINAR", "BUSCAR_ARCHIVO",
        "LINUX_APAGAR", "LINUX_REINICIAR", "LINUX_BLOQUEAR", "LINUX_CERRAR_SESION",
        "LINUX_VOL_UP", "LINUX_VOL_DOWN", "LINUX_VOL_MUTE",
        "LINUX_BRILLO_UP", "LINUX_BRILLO_DOWN", "LINUX_RAM", "LINUX_CPU",
        "LINUX_DISCO", "LINUX_PROCESOS", "LINUX_ACTUALIZAR",
        "GIT_PULL", "GIT_STATUS", "GIT_LOG", "GIT_PUSH",
        "DOCKER_UP", "DOCKER_DOWN", "LARAVEL_SERVE", "FLUTTER_RUN",
        "PYTHON_RUN",
        "HORA", "FECHA", "DIA_SEMANA", "MES", "AÑO",
        "CALCULAR", "DEFINIR",
    ],
    # Nivel 3: Aplicaciones
    [
        "ABRIR_APP",
    ],
    # Nivel 4: Preguntas
    [
        "BUSCAR_WEB",
    ],
    # Nivel 5: Conversación
    [
        "DESCANSAR", "CREAR_ALIAS",
    ],
]


def extraer_intencion(texto: str) -> tuple[Optional[str], float]:
    """
    Extrae la intención del texto respetando estrictamente la jerarquía de prioridad:
    1. Macros
    2. Intenciones especiales
    3. Aplicaciones
    4. Preguntas
    5. Conversación

    Args:
        texto: Texto normalizado y corregido.

    Returns:
        Tupla (intención, confianza). Intención es None si no se detecta.
    """
    # 1. Búsqueda exacta nivel por nivel de prioridad
    for nivel in NIVELES_PRIORIDAD:
        frases_nivel = [
            frase for intencion in nivel
            for frase in CATALOGO_INTENCIONES.get(intencion, [])
        ]
        # Frases más largas primero dentro del nivel
        for frase in sorted(frases_nivel, key=len, reverse=True):
            if frase in texto:
                intencion = _INDICE_EXACTO[frase]
                logger.debug("Intención exacta (Prioridad Nivel): '%s' (frase: '%s')", intencion, frase)
                return intencion, 100.0

    # 2. Búsqueda fuzzy nivel por nivel si no hubo coincidencia exacta
    for nivel in NIVELES_PRIORIDAD:
        frases_nivel = [
            frase for intencion in nivel
            for frase in CATALOGO_INTENCIONES.get(intencion, [])
        ]
        if not frases_nivel:
            continue

        match = rfprocess.extractOne(
            texto,
            frases_nivel,
            scorer=fuzz.partial_ratio,
            score_cutoff=UMBRAL_INTENCION,
        )
        if match:
            intencion = _INDICE_EXACTO[match[0]]
            confianza = match[1]
            logger.debug(
                "Intención fuzzy (Prioridad Nivel): '%s' (frase: '%s', score: %.1f)",
                intencion, match[0], confianza,
            )
            return intencion, confianza

    return None, 0.0




def extraer_entidades(texto: str, intencion: Optional[str]) -> dict:
    """
    Extrae entidades relevantes del texto según la intención detectada.

    Por ejemplo, para ABRIR_APP extrae el nombre de la aplicación.
    Para BUSCAR_WEB extrae el término de búsqueda.

    Args:
        texto: Texto normalizado.
        intencion: Intención ya detectada.

    Returns:
        Diccionario con entidades extraídas.
    """
    entidades: dict = {}

    if not intencion:
        return entidades

    # Verbos/disparadores a eliminar para extraer el objeto
    VERBOS_ABRIR = [
        "abre", "abrir", "ejecuta", "ejecutar", "lanza", "lanzar",
        "inicia", "iniciar", "quiero abrir", "necesito abrir", "podrías abrir",
        "puedes abrir", "pon", "arranca", "activa", "la aplicación",
        "el programa", "haz el favor de abrir", "abre por favor",
    ]
    VERBOS_BUSCAR = [
        "busca", "buscar", "googlea", "investiga", "búscame",
        "quiero saber sobre", "información sobre", "dime sobre",
        "busca información de", "en google",
    ]
    VERBOS_DEFINIR = [
        "que significa", "define", "que es", "significado de", "definicion de",
        "que quiere decir", "explicame",
    ]
    VERBOS_CALCULAR = [
        "cuanto es", "calcula", "cuantos son", "resultado de", "resuelve",
        "cuanto da", "opera", "cuanto vale", "calcúlame", "saca",
    ]
    VERBOS_CARPETA = [
        "abre la carpeta", "abre mi carpeta", "ve a", "abre",
        "muéstrame la carpeta", "ir a la carpeta", "ir a",
    ]
    VERBOS_CREAR_CARPETA = [
        "crea una carpeta llamada", "crea una carpeta", "nueva carpeta",
        "crear carpeta", "crea la carpeta", "haz una carpeta llamada",
        "haz una carpeta",
    ]
    VERBOS_CREAR_ARCHIVO = [
        "crea un archivo llamado", "crea un archivo", "nuevo archivo",
        "crear archivo", "haz un archivo",
    ]

    def limpiar_verbos(t: str, verbos: list[str]) -> str:
        for v in sorted(verbos, key=len, reverse=True):
            if t.startswith(v):
                t = t[len(v):].strip()
                break
        return t.strip()

    if intencion == "ABRIR_APP":
        nombre = limpiar_verbos(texto, VERBOS_ABRIR)
        entidades["app"] = nombre

    elif intencion == "BUSCAR_WEB":
        query = limpiar_verbos(texto, VERBOS_BUSCAR)
        entidades["query"] = query

    elif intencion == "ABRIR_WEB":
        sitio = limpiar_verbos(texto, ["abre", "ve a", "ir a", "navega a",
                                        "entra a", "visita", "abre la pagina",
                                        "abre el sitio"])
        entidades["sitio"] = sitio

    elif intencion == "DEFINIR":
        palabra = limpiar_verbos(texto, VERBOS_DEFINIR)
        entidades["palabra"] = palabra

    elif intencion == "CALCULAR":
        expresion = limpiar_verbos(texto, VERBOS_CALCULAR)
        entidades["expresion"] = expresion

    elif intencion == "ABRIR_CARPETA":
        carpeta = limpiar_verbos(texto, VERBOS_CARPETA)
        entidades["carpeta"] = carpeta

    elif intencion == "CREAR_CARPETA":
        nombre = limpiar_verbos(texto, VERBOS_CREAR_CARPETA)
        # Manejar "llamada X" al final
        nombre = re.sub(r"^llamad[ao]\s+", "", nombre).strip()
        entidades["nombre"] = nombre

    elif intencion == "CREAR_ARCHIVO":
        nombre = limpiar_verbos(texto, VERBOS_CREAR_ARCHIVO)
        nombre = re.sub(r"^llamad[ao]\s+", "", nombre).strip()
        entidades["nombre"] = nombre

    elif intencion in ("RENOMBRAR", "MOVER", "COPIAR", "ELIMINAR", "BUSCAR_ARCHIVO"):
        # Extraer objeto directamente
        verbos_map = {
            "RENOMBRAR": ["renombra", "renombrar", "cambia el nombre", "cambia nombre"],
            "MOVER": ["mueve", "mover", "traslada", "lleva", "pasa a"],
            "COPIAR": ["copia", "copiar", "duplica"],
            "ELIMINAR": ["elimina", "eliminar", "borra", "borrar", "quita"],
            "BUSCAR_ARCHIVO": ["busca el archivo", "encuentra", "donde esta",
                                "busca la carpeta", "localiza"],
        }
        verbs = verbos_map.get(intencion, [])
        obj = limpiar_verbos(texto, verbs)
        entidades["objeto"] = obj

    elif intencion in ("GIT_PULL", "GIT_STATUS", "GIT_LOG", "GIT_PUSH"):
        entidades["git_cmd"] = intencion.lower().replace("git_", "git ").replace("_", " ")

    elif intencion == "CERRAR_APP":
        app = limpiar_verbos(texto, ["cierra", "cerrar", "cierra la aplicación",
                                      "cierra el programa", "cierra la ventana",
                                      "cerrar aplicación", "cerrar programa"])
        entidades["app"] = app

    elif intencion == "ENFOCAR_APP" or intencion == "CAMBIAR_VENTANA":
        app = limpiar_verbos(texto, ["cambiar a", "enfocar", "cambia a",
                                      "pon en primer plano", "muéstrame", "trae",
                                      "trae a primer plano", "trae al frente",
                                      "al frente", "enfoca"])
        app = re.sub(r"\s+al\s+frente$", "", app).strip()
        app = re.sub(r"\s+a\s+primer\s+plano$", "", app).strip()
        entidades["app"] = app

    elif intencion == "MINIMIZAR_APP":
        app = limpiar_verbos(texto, ["minimiza", "minimizar", "minimiza la ventana",
                                      "minimiza el programa"])
        entidades["app"] = app

    elif intencion == "MAXIMIZAR_APP":
        app = limpiar_verbos(texto, ["maximiza", "maximizar", "maximiza la ventana",
                                      "maximiza el programa"])
        entidades["app"] = app

    elif intencion == "LARAVEL_SERVE":
        entidades["cmd"] = "php artisan serve"

    elif intencion == "FLUTTER_RUN":
        entidades["cmd"] = "flutter run"

    return entidades


def analizar(texto_crudo: str) -> ResultadoNLP:
    """
    Función principal de NLP. Procesa texto crudo y devuelve un ResultadoNLP
    completo con intención, confianza y entidades.

    Args:
        texto_crudo: Texto tal como vino del reconocedor de voz.

    Returns:
        ResultadoNLP con todos los campos completados.
    """
    texto_norm = normalizar(texto_crudo)
    texto_corr = corregir_fonetico(texto_norm)
    intencion, confianza = extraer_intencion(texto_corr)
    entidades = extraer_entidades(texto_corr, intencion)

    resultado = ResultadoNLP(
        texto_original=texto_crudo,
        texto_normalizado=texto_corr,
        intencion=intencion,
        confianza=confianza,
        entidades=entidades,
    )

    logger.info(
        "NLP: '%s' → intent=%s (%.0f%%) ent=%s",
        texto_crudo, intencion, confianza, entidades,
    )
    return resultado

