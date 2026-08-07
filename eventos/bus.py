"""
eventos/bus.py — EventBus thread-safe para Jarvis.

Implementa un bus de eventos pub/sub que permite al núcleo del asistente
comunicarse con la interfaz gráfica sin acoplamiento directo.

Diseño:
  - El cerebro/voz emiten eventos (publicar)
  - La UI suscribe callbacks (suscribir)
  - Los callbacks de la UI se ejecutan en el hilo de GLib mediante GLib.idle_add
    para garantizar thread-safety con GTK4
  - Sin GTK, los callbacks se ejecutan directamente (modo consola)

Eventos estándar del sistema Jarvis:
  jarvis.reposo           → Jarvis entró en modo espera
  jarvis.despertando      → Se detectó la wake word
  jarvis.escuchando       → Sesión activa, esperando comando
  jarvis.procesando       → Analizando texto con NLP
  jarvis.intencion        → Intención detectada (datos: intencion, confianza)
  jarvis.ejecutando       → Ejecutando acción (datos: accion, descripcion)
  jarvis.hablando         → TTS activo (datos: texto)
  jarvis.exito            → Acción completada (datos: resultado)
  jarvis.error            → Error en ejecución (datos: mensaje)
  jarvis.esperando        → Esperando confirmación del usuario
  jarvis.progreso_macro   → Progreso de macro (datos: paso, ok, descripcion)
  jarvis.texto_usuario    → Texto reconocido (datos: texto)
  jarvis.cambio_tema      → Tema/paleta cambiado (datos: nombre_tema)
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("jarvis.eventos.bus")


class EventBus:
    """
    Bus de eventos pub/sub thread-safe.

    Permite al núcleo de Jarvis comunicarse con la UI sin importaciones circulares
    ni acoplamiento directo entre capas.

    Uso:
        # Suscribirse (generalmente desde la UI)
        bus.suscribir("jarvis.escuchando", callback_fn)

        # Emitir (desde el núcleo)
        bus.emitir("jarvis.escuchando", datos={"info": "activo"})
    """

    def __init__(self) -> None:
        self._suscriptores: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._usar_glib: bool = False
        self._glib_idle_add: Optional[Callable] = None

    def configurar_glib(self, idle_add_fn: Callable) -> None:
        """
        Configura integración con GLib para thread-safety con GTK4.

        Llamar desde la UI antes de suscribirse:
            from gi.repository import GLib
            bus.configurar_glib(GLib.idle_add)

        Args:
            idle_add_fn: Función GLib.idle_add para ejecución en hilo principal GTK.
        """
        self._glib_idle_add = idle_add_fn
        self._usar_glib = True
        logger.info("EventBus configurado con GLib.idle_add para thread-safety GTK4.")

    def suscribir(self, evento: str, callback: Callable) -> None:
        """
        Suscribe un callback a un evento.

        Args:
            evento: Nombre del evento (e.g. 'jarvis.escuchando').
            callback: Función a llamar cuando se emita el evento.
                      Firma: callback(evento: str, datos: dict)
        """
        with self._lock:
            if evento not in self._suscriptores:
                self._suscriptores[evento] = []
            if callback not in self._suscriptores[evento]:
                self._suscriptores[evento].append(callback)
                logger.debug("Suscriptor registrado: %s → %s", evento, callback.__name__)

    def desuscribir(self, evento: str, callback: Callable) -> None:
        """
        Elimina un callback de un evento.

        Args:
            evento: Nombre del evento.
            callback: Callback a eliminar.
        """
        with self._lock:
            if evento in self._suscriptores:
                try:
                    self._suscriptores[evento].remove(callback)
                except ValueError:
                    pass

    def emitir(self, evento: str, datos: Optional[Dict[str, Any]] = None) -> None:
        """
        Emite un evento a todos sus suscriptores.

        Thread-safe: Si se configuró GLib, los callbacks se ejecutan en el
        hilo principal de GTK usando GLib.idle_add.

        Args:
            evento: Nombre del evento.
            datos: Diccionario con datos adicionales del evento.
        """
        if datos is None:
            datos = {}

        logger.debug("Evento emitido: '%s' datos=%s", evento, datos)

        with self._lock:
            callbacks = list(self._suscriptores.get(evento, []))
            # También notificar suscriptores del evento comodín "*"
            callbacks += list(self._suscriptores.get("*", []))

        for callback in callbacks:
            try:
                if self._usar_glib and self._glib_idle_add:
                    # Ejecutar en hilo GTK principal para thread-safety
                    self._glib_idle_add(self._ejecutar_callback, callback, evento, datos)
                else:
                    callback(evento, datos)
            except Exception as e:
                logger.error(
                    "Error ejecutando callback '%s' para evento '%s': %s",
                    getattr(callback, '__name__', str(callback)), evento, e
                )

    @staticmethod
    def _ejecutar_callback(callback: Callable, evento: str, datos: dict) -> bool:
        """
        Wrapper para GLib.idle_add. Retorna False para ejecutar solo una vez.
        """
        try:
            callback(evento, datos)
        except Exception as e:
            logger.error("Error en callback GTK: %s", e)
        return False  # GLib.idle_add: False = no repetir

    def limpiar(self) -> None:
        """Elimina todos los suscriptores. Útil para tests."""
        with self._lock:
            self._suscriptores.clear()

    def listar_eventos(self) -> List[str]:
        """Devuelve la lista de eventos con suscriptores activos."""
        with self._lock:
            return list(self._suscriptores.keys())


# ─────────────────────────────────────────────────────────────────────────────
# INSTANCIA SINGLETON GLOBAL
# ─────────────────────────────────────────────────────────────────────────────

bus = EventBus()


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DE EVENTOS
# ─────────────────────────────────────────────────────────────────────────────

class Eventos:
    """Constantes de nombres de eventos para evitar strings mágicos."""
    REPOSO               = "jarvis.reposo"
    DESPERTANDO          = "jarvis.despertando"
    ESCUCHANDO           = "jarvis.escuchando"
    PROCESANDO           = "jarvis.procesando"
    INTENCION            = "jarvis.intencion"
    EJECUTANDO           = "jarvis.ejecutando"
    HABLANDO             = "jarvis.hablando"
    FIN_HABLA            = "jarvis.fin_habla"
    EXITO                = "jarvis.exito"
    ERROR                = "jarvis.error"
    ESPERANDO            = "jarvis.esperando"
    PROGRESO_MACRO       = "jarvis.progreso_macro"
    TEXTO_USUARIO        = "jarvis.texto_usuario"
    CAMBIO_TEMA          = "jarvis.cambio_tema"
    MACRO_INICIADA       = "jarvis.macro_iniciada"
    MACRO_COMPLETADA     = "jarvis.macro_completada"
    AUDIO_LEVEL          = "jarvis.audio_level"
    MICROPHONE_ACTIVE    = "jarvis.microphone_active"
    MICROPHONE_IDLE      = "jarvis.microphone_idle"
    STATE_CHANGED        = "jarvis.state.changed"
    VOICE_STARTED        = "jarvis.voice.started"
    VOICE_FINISHED       = "jarvis.voice.finished"
    COMMAND_RECEIVED     = "jarvis.command.received"
    COMMAND_COMPLETED    = "jarvis.command.completed"
    APPLICATION_DETECTED = "jarvis.application.detected"
    APPLICATION_OPENED   = "jarvis.application.opened"
    APPLICATION_CLOSED   = "jarvis.application.closed"
    COMODIN              = "*"
