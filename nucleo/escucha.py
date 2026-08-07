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

from config import (
    IDIOMA_STR,
    TIMEOUT_ESCUCHA,
    PHRASE_TIME_LIMIT,
    AJUSTE_RUIDO_DURATION,
)

logger = logging.getLogger("jarvis.escucha")


class Escuchador:
    """
    Gestiona el reconocimiento de voz con calibración de ruido reutilizable.

    El ajuste de ruido ambiental se realiza una sola vez al crear la instancia
    (o puede forzarse con `recalibrar()`), reduciendo la latencia de ~1s por ciclo.
    """

    def __init__(self) -> None:
        self._reconocedor = sr.Recognizer()
        self._calibrado = False

    def recalibrar(self) -> None:
        """
        Recalibra el nivel de ruido ambiental.
        Llamar si el entorno cambia significativamente.
        """
        print("[🎤 Calibrando ruido ambiental...]")
        logger.info("Recalibrando ruido ambiental.")
        with sr.Microphone() as origen:
            self._reconocedor.adjust_for_ambient_noise(
                origen, duration=AJUSTE_RUIDO_DURATION
            )
        self._calibrado = True
        logger.info("Calibración completada.")

    def escuchar(self) -> str | None:
        """
        Escucha el micrófono y devuelve el texto reconocido.

        Realiza la calibración de ruido en el primer uso automáticamente.

        Returns:
            Texto reconocido en minúsculas, o None si no se detectó habla
            o no se pudo reconocer.
        """
        if not self._calibrado:
            self.recalibrar()

        try:
            with sr.Microphone() as origen:
                print("[👂 Escuchando...]")
                audio = self._reconocedor.listen(
                    origen,
                    timeout=TIMEOUT_ESCUCHA,
                    phrase_time_limit=PHRASE_TIME_LIMIT,
                )

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
            logger.error("Error inesperado en escucha: %s", e)
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