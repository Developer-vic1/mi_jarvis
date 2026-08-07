"""
nucleo/cerebro.py — Motor central de Jarvis. Máquina de estados conversacional.

Responsabilidades:
- Coordinar NLP → Plugin → Voz → Memoria → Log
- Gestionar el estado de la sesión conversacional
- Manejar confirmaciones pendientes (e.g. eliminación de archivos)
- Registrar cada interacción en logs y memoria
- Emitir eventos al EventBus para sincronizar la interfaz gráfica

Flujo:
    texto_crudo
        → NLP.analizar()
        → resolver_alias() (si existe)
        → obtener_plugin(intencion)
        → plugin.manejar()
        → voz.hablar()
        → memoria.guardar_interaccion()
        → EventBus.emitir()
        → logger
"""

import logging
import time
from enum import Enum, auto
from typing import Optional

from nucleo.nlp import analizar, ResultadoNLP
from nucleo.voz import hablar, hablar_contexto, frase_aleatoria
from nucleo.memoria import (
    guardar_interaccion,
    resolver_alias,
    registrar_app_usada,
)
from config import TIMEOUT_SESION, WAKE_WORDS, SLEEP_WORDS
from eventos.bus import bus, Eventos

import plugins
import plugins.aplicaciones    # noqa: F401 — cargar alias ALIASES_EXTRA
import plugins.ventanas        # noqa: F401
import plugins.linux           # noqa: F401
import plugins.web             # noqa: F401
import plugins.archivos        # noqa: F401
import plugins.calculadora     # noqa: F401
import plugins.datetime_info   # noqa: F401
import plugins.definiciones    # noqa: F401
import plugins.desarrollo      # noqa: F401
import plugins.ayuda           # noqa: F401

logger = logging.getLogger("jarvis.cerebro")


# ─────────────────────────────────────────────────────────────────────────────
# MÁQUINA DE ESTADOS
# ─────────────────────────────────────────────────────────────────────────────

class EstadoJarvis(Enum):
    """Estados posibles del asistente."""
    REPOSO = auto()               # Esperando wake word
    DESPERTANDO = auto()          # Detectó wake word, transición
    ESCUCHANDO = auto()           # Sesión activa, esperando comando
    PROCESANDO = auto()           # Analizando con NLP
    EJECUTANDO = auto()           # Ejecutando acción/plugin
    HABLANDO = auto()             # TTS activo
    EXITO = auto()                # Acción completada con éxito
    ERROR = auto()                # Error en ejecución
    ESPERANDO_CONFIRMACION = auto()  # Esperando "sí" o "no" del usuario


class Cerebro:
    """
    Motor central de Jarvis con gestión de estado conversacional.

    Ejemplo de uso:
        cerebro = Cerebro()
        cerebro.inicializar()
        respuesta = cerebro.procesar("abre chrome")
    """

    def __init__(self) -> None:
        self._estado = EstadoJarvis.REPOSO
        self._ultima_actividad = 0.0
        self._contexto: dict = {}           # Contexto de la sesión actual
        self._confirmacion_pendiente: Optional[dict] = None

    def inicializar(self) -> None:
        """
        Inicializa el cerebro: carga plugins y construye el índice de apps.
        Debe llamarse una vez al arrancar.
        """
        logger.info("Inicializando cerebro de Jarvis...")
        plugins.cargar_todos()
        from macros.gestor_macros import cargar_macros
        cargar_macros()
        logger.info(
            "Plugins cargados: %d (%d intenciones).",
            len(plugins.listar_plugins()),
            sum(len(p.intenciones) for p in plugins.listar_plugins()),
        )

    @property
    def estado(self) -> EstadoJarvis:
        return self._estado

    @property
    def sesion_activa(self) -> bool:
        """True si la sesión está activa (no en reposo) y no ha expirado."""
        if self._estado == EstadoJarvis.REPOSO:
            return False
        elapsed = time.time() - self._ultima_actividad
        return elapsed < TIMEOUT_SESION

    def _activar_sesion(self) -> None:
        """Activa la sesión conversacional."""
        self._estado = EstadoJarvis.DESPERTANDO
        bus.emitir(Eventos.DESPERTANDO)
        time.sleep(0.1)  # Pequeña pausa para que la UI reaccione
        self._estado = EstadoJarvis.ESCUCHANDO
        self._ultima_actividad = time.time()
        self._contexto = {}
        bus.emitir(Eventos.ESCUCHANDO)
        logger.info("Sesión activada.")

    def _actualizar_actividad(self) -> None:
        """Actualiza el timestamp de última actividad para evitar timeout."""
        self._ultima_actividad = time.time()

    def _desactivar_sesion(self) -> None:
        """Pone a Jarvis en modo reposo."""
        self._estado = EstadoJarvis.REPOSO
        self._contexto = {}
        self._confirmacion_pendiente = None
        bus.emitir(Eventos.REPOSO)
        logger.info("Sesión desactivada. Modo reposo.")

    def _timeout_expirado(self) -> bool:
        """Verifica si la sesión ha expirado por inactividad."""
        if self._estado == EstadoJarvis.REPOSO:
            return False
        return (time.time() - self._ultima_actividad) >= TIMEOUT_SESION

    def verificar_timeout(self) -> bool:
        """
        Verifica y maneja el timeout de sesión.

        Returns:
            True si la sesión expiró y Jarvis fue a reposo.
        """
        if self._timeout_expirado():
            logger.info("Sesión expirada por inactividad.")
            self._desactivar_sesion()
            return True
        return False

    def es_wake_word(self, texto: str) -> bool:
        """
        Verifica si el texto contiene una wake word.

        Args:
            texto: Texto normalizado del usuario.

        Returns:
            True si contiene una wake word.
        """
        texto_norm = texto.lower().strip()
        return any(w in texto_norm for w in WAKE_WORDS)

    def es_sleep_word(self, texto: str) -> bool:
        """
        Verifica si el texto es una instrucción de reposo.

        Args:
            texto: Texto normalizado del usuario.

        Returns:
            True si es una instrucción de reposo.
        """
        texto_norm = texto.lower().strip()
        return any(w in texto_norm for w in SLEEP_WORDS)

    def _extraer_tras_wake_word(self, texto: str) -> str:
        """
        Extrae el comando que va después de la wake word.

        Ejemplo: "jarvis abre chrome" → "abre chrome"

        Args:
            texto: Texto completo incluyendo wake word.

        Returns:
            Texto del comando sin la wake word, o string vacío.
        """
        texto_lower = texto.lower().strip()
        for wake in sorted(WAKE_WORDS, key=len, reverse=True):
            if texto_lower.startswith(wake):
                resto = texto[len(wake):].strip()
                return resto
        return ""

    def _manejar_confirmacion(self, texto: str) -> Optional[str]:
        """
        Maneja respuestas de confirmación (sí/no) cuando hay acción pendiente.

        Args:
            texto: Respuesta del usuario.

        Returns:
            Respuesta de Jarvis o None si no había confirmación pendiente.
        """
        if not self._confirmacion_pendiente:
            return None

        texto_lower = texto.lower().strip()
        datos = self._confirmacion_pendiente
        self._confirmacion_pendiente = None
        self._estado = EstadoJarvis.ESCUCHANDO

        respuestas_si = ["sí", "si", "confirmo", "correcto", "adelante",
                          "procede", "claro", "dale", "ok", "okay", "sí por favor"]
        respuestas_no = ["no", "cancela", "cancelar", "mejor no", "olvídalo",
                          "no gracias", "espera", "para"]

        if any(r in texto_lower for r in respuestas_si):
            # Ejecutar la acción confirmada
            accion = datos.get("accion")
            if accion == "eliminar":
                from plugins.archivos import PluginArchivos
                plugin_arch = PluginArchivos()
                resultado = plugin_arch.confirmar_eliminar(datos["ruta"])
                return resultado
            return "Acción confirmada."

        elif any(r in texto_lower for r in respuestas_no):
            return "Acción cancelada. No se hizo nada."

        return "No entendí la respuesta. Di 'sí' para confirmar o 'no' para cancelar."

    def procesar(self, texto_crudo: str) -> Optional[str]:
        """
        Procesa un texto del usuario y devuelve la respuesta de Jarvis.

        Esta es la función principal del cerebro. Maneja el ciclo completo:
        NLP → Plugin → Respuesta → Memoria.

        Args:
            texto_crudo: Texto tal como viene del reconocedor de voz.

        Returns:
            Texto de respuesta, o None si no hay nada que decir.
        """
        if not texto_crudo or not texto_crudo.strip():
            return None

        logger.info("Procesando: '%s' (estado=%s)", texto_crudo, self._estado.name)

        # ── Verificar timeout ─────────────────────────────────────────────────
        if self.verificar_timeout():
            hablar_contexto("reposo")
            return None

        # ── Estado REPOSO: solo escuchar wake word ────────────────────────────
        if self._estado == EstadoJarvis.REPOSO:
            if self.es_wake_word(texto_crudo):
                self._activar_sesion()
                comando_inline = self._extraer_tras_wake_word(texto_crudo)
                hablar_contexto("activado")
                if comando_inline:
                    # "Jarvis, abre chrome" → procesar "abre chrome" inmediatamente
                    return self._procesar_comando(comando_inline)
                return None
            # Ignorar silenciosamente si no es wake word
            return None

        # ── Estado ESPERANDO_CONFIRMACION ─────────────────────────────────────
        if self._estado == EstadoJarvis.ESPERANDO_CONFIRMACION:
            self._actualizar_actividad()
            respuesta = self._manejar_confirmacion(texto_crudo)
            if respuesta:
                hablar(respuesta)
                guardar_interaccion(texto_crudo, "CONFIRMACION", respuesta)
            return respuesta

        # ── Estado ESCUCHANDO: procesar comando ───────────────────────────────
        if self._estado == EstadoJarvis.ESCUCHANDO:
            self._actualizar_actividad()

            # Verificar si es sleep word
            if self.es_sleep_word(texto_crudo):
                self._desactivar_sesion()
                hablar_contexto("reposo")
                guardar_interaccion(texto_crudo, "DESCANSAR", "Modo reposo")
                return None

            return self._procesar_comando(texto_crudo)

        return None

    def _procesar_comando(self, texto_crudo: str) -> Optional[str]:
        """
        Procesa un comando específico (sin gestión de estado).

        Flujo: resolver_alias → NLP → Plugin → Respuesta

        Args:
            texto_crudo: Texto del comando.

        Returns:
            Texto de respuesta o None.
        """
        self._estado = EstadoJarvis.PROCESANDO
        bus.emitir(Eventos.TEXTO_USUARIO, {"texto": texto_crudo})
        bus.emitir(Eventos.PROCESANDO, {"texto": texto_crudo})

        try:
            # ── 1. Resolver alias ─────────────────────────────────────────────
            comando_real = resolver_alias(texto_crudo)
            if comando_real:
                logger.info("Alias resuelto: '%s' → '%s'", texto_crudo, comando_real)
                texto_crudo = comando_real

            # ── 2. Análisis NLP ───────────────────────────────────────────────
            resultado_nlp = analizar(texto_crudo)

            print(
                f"\n  🧠 NLP: '{resultado_nlp.texto_normalizado}' "
                f"→ intención={resultado_nlp.intencion} "
                f"({resultado_nlp.confianza:.0f}%) "
                f"entidades={resultado_nlp.entidades}"
            )

            # Emitir intención detectada
            bus.emitir(Eventos.INTENCION, {
                "intencion": resultado_nlp.intencion or "DESCONOCIDO",
                "confianza": resultado_nlp.confianza,
                "texto_normalizado": resultado_nlp.texto_normalizado,
                "entidades": resultado_nlp.entidades,
            })

            # ── 3. Si no hay intención clara ──────────────────────────────────
            if not resultado_nlp.tiene_intencion:
                respuesta = frase_aleatoria("sin_funcion")
                hablar(respuesta)
                guardar_interaccion(texto_crudo, "DESCONOCIDO", respuesta)
                self._estado = EstadoJarvis.ESCUCHANDO
                bus.emitir(Eventos.ESCUCHANDO)
                return respuesta

            # ── 3.5 Enrutamiento mediante Motor de Macros ────────────────────
            from macros.gestor_macros import es_macro, ejecutar_macro
            if resultado_nlp.intencion and es_macro(resultado_nlp.intencion):
                self._estado = EstadoJarvis.EJECUTANDO
                bus.emitir(Eventos.MACRO_INICIADA, {"intencion": resultado_nlp.intencion})
                bus.emitir(Eventos.EJECUTANDO, {
                    "accion": resultado_nlp.intencion,
                    "descripcion": f"Ejecutando macro {resultado_nlp.intencion}",
                })
                try:
                    exito, respuesta = ejecutar_macro(resultado_nlp.intencion)
                except Exception as e:
                    logger.error("Error al ejecutar macro %s: %s", resultado_nlp.intencion, e, exc_info=True)
                    respuesta = f"Ocurrió un error inesperado al ejecutar la macro {resultado_nlp.intencion}."
                    hablar(respuesta)
                    bus.emitir(Eventos.ERROR, {"mensaje": str(e)})

                if exito:
                    bus.emitir(Eventos.MACRO_COMPLETADA, {
                        "intencion": resultado_nlp.intencion,
                        "resultado": respuesta,
                        "exito": True,
                    })
                    bus.emitir(Eventos.EXITO, {"resultado": respuesta})
                else:
                    bus.emitir(Eventos.MACRO_COMPLETADA, {
                        "intencion": resultado_nlp.intencion,
                        "resultado": respuesta,
                        "exito": False,
                    })

                guardar_interaccion(texto_crudo, resultado_nlp.intencion, respuesta)
                self._estado = EstadoJarvis.ESCUCHANDO
                bus.emitir(Eventos.ESCUCHANDO)
                return respuesta

            # ── 4. Buscar plugin ──────────────────────────────────────────────

            plugin = plugins.obtener_plugin(resultado_nlp.intencion)

            if not plugin:
                respuesta = f"Entendí que quieres {resultado_nlp.intencion}, pero aún no tengo esa función implementada."
                hablar(respuesta)
                guardar_interaccion(texto_crudo, resultado_nlp.intencion, respuesta)
                self._estado = EstadoJarvis.ESCUCHANDO
                bus.emitir(Eventos.ESCUCHANDO)
                return respuesta

            # ── 5. Ejecutar plugin ────────────────────────────────────────────
            self._estado = EstadoJarvis.EJECUTANDO
            bus.emitir(Eventos.EJECUTANDO, {
                "accion": resultado_nlp.intencion,
                "descripcion": f"Plugin: {type(plugin).__name__}",
            })
            respuesta_raw = plugin.manejar(
                resultado_nlp.intencion,
                resultado_nlp.entidades,
                self._contexto,
            )

            # ── 6. Procesar señales especiales de los plugins ─────────────────
            respuesta = self._procesar_respuesta_plugin(
                respuesta_raw, resultado_nlp
            )

            # ── 7. Registrar y vocalizar ──────────────────────────────────────
            if respuesta:
                hablar(respuesta)
                guardar_interaccion(
                    texto_crudo,
                    resultado_nlp.intencion or "",
                    respuesta,
                )
                bus.emitir(Eventos.EXITO, {"resultado": respuesta})

            self._estado = EstadoJarvis.ESCUCHANDO
            bus.emitir(Eventos.ESCUCHANDO)
            return respuesta

        except Exception as e:
            logger.error("Error inesperado en _procesar_comando: %s", e, exc_info=True)
            respuesta = "Hubo un problema al procesar tu solicitud."
            hablar(respuesta)
            self._estado = EstadoJarvis.ESCUCHANDO
            bus.emitir(Eventos.ERROR, {"mensaje": str(e)})
            bus.emitir(Eventos.ESCUCHANDO)
            return respuesta

    def _procesar_respuesta_plugin(
        self, respuesta_raw: str, resultado_nlp: ResultadoNLP
    ) -> str:
        """
        Procesa la respuesta devuelta por un plugin.

        Maneja señales especiales como:
        - '__abriendo__<app>' → usa frases naturales de contexto 'abriendo'
        - Respuestas de confirmación pendiente

        Args:
            respuesta_raw: Respuesta cruda del plugin.
            resultado_nlp: Resultado del análisis NLP.

        Returns:
            Respuesta final para el usuario.
        """
        if not respuesta_raw:
            return frase_aleatoria("exito")

        # ── Señal de apertura de app ──────────────────────────────────────────
        if respuesta_raw.startswith("__abriendo__"):
            nombre_app = respuesta_raw[len("__abriendo__"):]
            registrar_app_usada(nombre_app)
            frase = frase_aleatoria("abriendo")
            if frase.endswith("."):
                frase = frase[:-1]
            return f"{frase} {nombre_app}."

        # ── Verificar si hay confirmación pendiente en el contexto ────────────
        ruta_eliminar = self._contexto.pop("_confirmar_eliminar", None)
        if ruta_eliminar:
            self._confirmacion_pendiente = {
                "accion": "eliminar",
                "ruta": ruta_eliminar,
            }
            self._estado = EstadoJarvis.ESPERANDO_CONFIRMACION

        return respuesta_raw


# ─────────────────────────────────────────────────────────────────────────────
# INSTANCIA SINGLETON Y API FUNCIONAL
# ─────────────────────────────────────────────────────────────────────────────

_cerebro = Cerebro()


def inicializar() -> None:
    """Inicializa el cerebro. Llamar una vez al arrancar."""
    _cerebro.inicializar()


def procesar_comando(texto: str) -> Optional[str]:
    """
    Procesa un texto del usuario.
    Mantiene compatibilidad con el código legado que importa esta función.

    Args:
        texto: Texto del usuario.

    Returns:
        Respuesta de Jarvis o None.
    """
    return _cerebro.procesar(texto)


def activar_sesion() -> None:
    """Activa la sesión conversacional (útil para tests)."""
    _cerebro._activar_sesion()


def obtener_estado() -> EstadoJarvis:
    """Devuelve el estado actual del cerebro."""
    return _cerebro.estado


def sesion_activa() -> bool:
    """Devuelve True si hay sesión conversacional activa."""
    return _cerebro.sesion_activa


def verificar_timeout() -> bool:
    """Verifica si la sesión expiró."""
    return _cerebro.verificar_timeout()