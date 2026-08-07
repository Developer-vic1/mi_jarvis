"""
nucleo/escucha.py — Módulo de reconocimiento de voz de Jarvis.

Responsabilidades:
- Capturar audio del micrófono.
- Ajustar el ruido ambiental una sola vez al inicio (no en cada ciclo).
- Transcribir audio a texto usando Google Speech API.
- Manejar todos los errores posibles con respuestas informativas.
"""

import logging
import speech_recognition as sr  # type: ignore[import]

from eventos.bus import bus, Eventos

from config import (
    IDIOMA_STR,
    TIMEOUT_ESCUCHA,
    PHRASE_TIME_LIMIT,
    AJUSTE_RUIDO_DURATION,
)

from nucleo.audio_security import gestor_audio_security

logger = logging.getLogger("jarvis.escucha")


class Escuchador:
    """
    Gestiona el reconocimiento de voz con calibración de ruido reutilizable.
    Garantiza el uso exclusivo de micrófonos físicos autorizados.
    """

    def __init__(self) -> None:
        self._reconocedor = sr.Recognizer()
        self._calibrado = False
        self._microfono_disponible = True
        self._error_reportado = False

    def _reportar_microfono_no_disponible(self, detalle: str) -> None:
        self._microfono_disponible = False
        if not self._error_reportado:
            self._error_reportado = True
            logger.error("Micrófono físico no disponible: %s", detalle)
            bus.emitir(Eventos.ERROR, {"mensaje": "Micrófono no disponible"})

    def recalibrar(self) -> None:
        """
        Recalibra el nivel de ruido ambiental usando el micrófono físico resuelto.
        """
        idx, nombre = gestor_audio_security.resolver_microfono_fisico()
        if idx is None:
            self._reportar_microfono_no_disponible("No se encontró micrófono físico. Audio del sistema bloqueado.")
            return

        print(f"[🎤 Calibrando ruido ambiental en '{nombre}' (Índice {idx})...]")
        logger.info("Recalibrando ruido ambiental en micrófono físico índice %d.", idx)
        try:
            with sr.Microphone(device_index=idx) as origen:
                self._reconocedor.adjust_for_ambient_noise(
                    origen, duration=AJUSTE_RUIDO_DURATION
                )
        except Exception as e:
            self._reportar_microfono_no_disponible(str(e))
            raise
        self._calibrado = True
        self._microfono_disponible = True
        logger.info("Calibración completada.")

    def escuchar(self) -> str | None:
        """
        Escucha el micrófono físico y devuelve el texto reconocido.

        Auto-descarta captura si JARVIS está hablando (previene auto-escucha por TTS).

        Returns:
            Texto reconocido en minúsculas, o None.
        """
        if gestor_audio_security.esta_mic_pausado_por_tts():
            logger.debug("Escucha pausada: JARVIS está hablando mediante TTS.")
            return None

        idx, nombre = gestor_audio_security.resolver_microfono_fisico()
        if idx is None:
            self._reportar_microfono_no_disponible("No hay micrófono físico disponible. Sistema en modo seguro.")
            return None

        if not self._calibrado:
            try:
                self.recalibrar()
            except Exception:
                return None

        try:
            with sr.Microphone(device_index=idx) as origen:
                print(f"[👂 Escuchando en '{nombre}'...]")
                audio = self._reconocedor.listen(
                    origen,
                    timeout=TIMEOUT_ESCUCHA,
                    phrase_time_limit=PHRASE_TIME_LIMIT,
                )

            # Volver a verificar si empezó a hablar TTS durante el grabado
            if gestor_audio_security.esta_mic_pausado_por_tts():
                logger.debug("Audio grabado ignorado: TTS se activó durante la captura.")
                return None

            print("[⚙️  Procesando audio...]")
            texto = self._reconocedor.recognize_google(
                audio, language=IDIOMA_STR
            )
            texto = texto.strip().lower()
            logger.info("Texto reconocido: '%s'", texto)
            return texto

        except sr.WaitTimeoutError:
            logger.debug("Timeout: no se detectó habla.")
            return None

        except sr.UnknownValueError:
            logger.debug("Audio no reconocible.")
            return None

        except sr.RequestError as e:
            logger.error("Error en Google Speech API: %s", e)
            from nucleo.voz import hablar
            hablar("Tengo problemas de conexión con el servicio de reconocimiento.")
            return None

        except Exception as e:
            texto_error = str(e).lower()
            if "pyaudio" in texto_error or "input device" in texto_error or "default input" in texto_error:
                self._reportar_microfono_no_disponible(str(e))
            else:
                logger.error("Error inesperado en escucha: %s", e)
                bus.emitir(Eventos.ERROR, {"mensaje": f"Error de micrófono: {e}"})
            return None


# Instancia singleton para reutilizar en todo el sistema
_escuchador = Escuchador()


def escuchar_microfono() -> str | None:
    """
    Interfaz funcional para el escuchador singleton.
    Mantiene compatibilidad con el código legado que importa esta función.

    Returns:
        Texto reconocido en minúsculas, o None.
    """
    return _escuchador.escuchar()


def recalibrar_microfono() -> None:
    """Fuerza recalibración de ruido ambiental."""
    _escuchador.recalibrar()
