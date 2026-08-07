"""
nucleo/voz.py — Módulo de síntesis de voz (TTS) de Jarvis.

Responsabilidades:
- Sintetizar texto a audio usando Piper TTS.
- Proporcionar un pool de respuestas naturales variadas para cada contexto.
- Garantizar que Jarvis nunca suene robótico ni repita siempre la misma frase.
- Proteger contra shell injection usando subprocess con lista de argumentos.
"""

import os
import random
import subprocess
import logging
from typing import Optional

from config import MODELO_VOZ, SAMPLE_RATE_VOZ
from eventos.bus import bus, Eventos

logger = logging.getLogger("jarvis.voz")

# ─────────────────────────────────────────────────────────────────────────────
# POOL DE RESPUESTAS NATURALES
# Agrupadas por contexto semántico. Jarvis elige aleatoriamente de cada grupo.
# ─────────────────────────────────────────────────────────────────────────────

_FRASES: dict[str, list[str]] = {
    # ── Confirmación positiva / inicio de acción ──────────────────────────────
    "confirmacion": [
        "Claro.", "Perfecto.", "Enseguida.", "Con gusto.", "Ahora mismo.",
        "En seguida.", "Cómo no.", "Por supuesto.", "Entendido.",
        "Sin problema.", "Marchando.", "Voy a ello.", "Déjame hacer eso.",
        "Listo para ejecutar.", "Recibido.", "Procesando tu orden.",
        "Justo lo que necesitas.", "Está bien.", "Cuenta con ello.",
        "Inmediatamente.", "Ya me encargo.", "A la orden.",
    ],

    # ── Éxito / acción completada ─────────────────────────────────────────────
    "exito": [
        "Listo.", "Ya está.", "He terminado.", "Misión cumplida.",
        "Todo correcto.", "Hecho.", "Ya está listo.", "Completado.",
        "Sin inconvenientes.", "Fue sencillo.", "Eso fue fácil.",
        "Ejecutado correctamente.", "Todo en orden.", "Ya quedó.",
        "Está hecho.", "No hubo problema.", "Perfecto, todo bien.",
        "Funcionó a la primera.", "Completado con éxito.",
    ],

    # ── Buscando / procesando ─────────────────────────────────────────────────
    "buscando": [
        "Déjame buscarlo.", "Estoy buscando esa información.",
        "Un momento, lo busco.", "Revisando...", "Dame un segundo.",
        "Consultando...", "Estoy en ello.", "Espera un momento.",
        "Buscando resultados.", "Un instante.", "Lo estoy procesando.",
        "Revisando la información.", "Consultando los datos.",
    ],

    # ── Abriendo aplicación / carpeta ─────────────────────────────────────────
    "abriendo": [
        "Abriendo.", "En un momento.", "Iniciando.", "Cargando.",
        "Lanzando la aplicación.", "Aquí vamos.", "Encendiendo.",
        "Ejecutando.", "Ya lo abro.", "Un segundo.", "Arrancando.",
        "Activando.", "Ya está en camino.", "Iniciando el programa.",
    ],

    # ── Error / no encontrado ─────────────────────────────────────────────────
    "error": [
        "Hubo un problema.", "Encontré un inconveniente.",
        "No pude completarlo.", "Algo falló.", "Surgió un error.",
        "No logré ejecutarlo.", "Tuve un problema con eso.",
        "No fue posible completar la acción.",
    ],

    # ── No encontrado ─────────────────────────────────────────────────────────
    "no_encontrado": [
        "No encontré nada.", "No encontré esa aplicación.",
        "No hay resultados.", "No tengo información sobre eso.",
        "No lo encontré en el sistema.", "No existe en mis registros.",
        "No logré localizar eso.", "No está disponible.",
        "No encontré lo que buscas.",
    ],

    # ── Pidiendo aclaración ───────────────────────────────────────────────────
    "aclaracion": [
        "¿Puedes repetirlo?", "No entendí bien. ¿Podrías repetirlo?",
        "¿Me lo repites, por favor?", "No capté bien. ¿Qué dijiste?",
        "No comprendí. ¿Qué necesitas?", "¿Podrías ser más específico?",
        "¿Me das más detalles?", "No estoy seguro de haber entendido.",
    ],

    # ── Múltiples resultados ──────────────────────────────────────────────────
    "multiples": [
        "Encontré varias opciones.", "Hay más de una coincidencia.",
        "Encontré varios resultados.", "Tengo varias opciones disponibles.",
        "Hay múltiples opciones.", "Encontré más de uno.",
    ],

    # ── Pregunta de confirmación ──────────────────────────────────────────────
    "confirmar": [
        "¿Confirmas?", "¿Estás seguro?", "¿Deseas continuar?",
        "¿Procedo?", "¿Confirmas la operación?", "¿Quieres que lo haga?",
        "¿Doy el paso?", "¿Continúo?",
    ],

    # ── Saludo de inicio ──────────────────────────────────────────────────────
    "saludo": [
        "Sistemas en línea. ¿En qué te ayudo?",
        "Jarvis activo. Listo para trabajar.",
        "Aquí estoy. ¿Qué necesitas?",
        "En línea. ¿Cómo puedo ayudarte?",
        "Sistemas operativos. A tu disposición.",
        "Activo y listo. Dime.",
        "Jarvis al servicio. ¿Qué necesitas?",
        "Encendido. ¿En qué puedo ayudar?",
    ],

    # ── Reposo / despedida ────────────────────────────────────────────────────
    "reposo": [
        "Descansando. Llámame cuando me necesites.",
        "En modo reposo. Dime 'Jarvis' cuando necesites algo.",
        "Descansando. Estaré aquí.",
        "Modo reposo activado.",
        "Me quedo en reposo. Avísame.",
        "Aquí estaré cuando me necesites.",
    ],

    # ── Modo activo (al activar por wake word) ────────────────────────────────
    "activado": [
        "Dime.", "¿En qué puedo ayudarte?", "Te escucho.",
        "Sí, dime.", "A tus órdenes.", "¿Qué necesitas?",
        "Aquí estoy.", "Adelante.", "Escuchando.",
        "Cuéntame.", "Dime qué necesitas.",
    ],

    # ── No tiene esa función ──────────────────────────────────────────────────
    "sin_funcion": [
        "Aún no sé hacer eso, pero puedo aprender.",
        "Esa función no la tengo implementada todavía.",
        "No tengo una acción asignada para eso.",
        "No sé hacer eso aún. ¿Puedo ayudarte con algo más?",
        "Eso está fuera de mis capacidades por el momento.",
    ],

    # ── Reintentar ────────────────────────────────────────────────────────────
    "reintento": [
        "Voy a intentarlo nuevamente.", "Lo intento otra vez.",
        "Permíteme reintentar.", "Deja que lo pruebe de nuevo.",
    ],
}

# Historial de últimas frases para evitar repetición inmediata
_ultimo_usada: dict[str, str] = {}


def frase_aleatoria(contexto: str = "confirmacion") -> str:
    """
    Devuelve una frase aleatoria del contexto indicado,
    evitando repetir la última frase usada en ese contexto.

    Args:
        contexto: Clave del grupo de frases (e.g. 'exito', 'error').

    Returns:
        Frase aleatoria seleccionada del pool.
    """
    opciones = _FRASES.get(contexto, _FRASES["confirmacion"])

    if len(opciones) == 1:
        return opciones[0]

    ultima = _ultimo_usada.get(contexto)
    candidatas = [f for f in opciones if f != ultima]
    elegida = random.choice(candidatas)
    _ultimo_usada[contexto] = elegida
    return elegida


def hablar(texto: str) -> None:
    """
    Sintetiza y reproduce el texto usando Piper TTS + aplay.

    Emite eventos jarvis.hablando al inicio y jarvis.fin_habla al terminar.
    Usa subprocess con lista de argumentos para evitar shell injection.
    Si el modelo de voz no está disponible, solo imprime en consola.

    Args:
        texto: Texto a sintetizar. Puede contener cualquier carácter.
    """
    print(f"\n🤖 Jarvis: {texto}")
    logger.info("TTS: %s", texto)

    # Notificar a la UI que Jarvis está hablando
    bus.emitir(Eventos.HABLANDO, {"texto": texto})

    if not os.path.exists(MODELO_VOZ):
        logger.warning("Modelo de voz no encontrado: %s", MODELO_VOZ)
        bus.emitir(Eventos.FIN_HABLA, {"texto": texto})
        return

    try:
        # Encontrar el ejecutable piper dentro del venv
        venv_piper = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "venv", "bin", "piper"
        )
        piper_cmd = venv_piper if os.path.exists(venv_piper) else "piper"

        # Piper: lee desde stdin, escribe PCM raw en stdout
        proc_piper = subprocess.Popen(
            [piper_cmd, "--model", MODELO_VOZ, "--output-raw"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        # aplay: lee PCM raw desde stdin y lo reproduce
        proc_aplay = subprocess.Popen(
            ["aplay", "-r", str(SAMPLE_RATE_VOZ), "-f", "S16_LE", "-t", "raw", "-"],
            stdin=proc_piper.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Enviar texto a piper y esperar
        if proc_piper.stdin:
            proc_piper.stdin.write(texto.encode("utf-8"))
            proc_piper.stdin.close()

        proc_piper.wait()
        proc_aplay.wait()

    except FileNotFoundError:
        logger.error("No se encontró el ejecutable piper.")
    except Exception as e:
        logger.error("Error en TTS: %s", e)
    finally:
        # Siempre notificar que terminó de hablar
        bus.emitir(Eventos.FIN_HABLA, {"texto": texto})


def hablar_contexto(contexto: str, sufijo: Optional[str] = None) -> None:
    """
    Habla una frase aleatoria del contexto especificado,
    opcionalmente concatenando un sufijo informativo.

    Args:
        contexto: Clave del grupo de frases.
        sufijo: Texto adicional a añadir tras la frase aleatoria.

    Ejemplo:
        hablar_contexto("abriendo", "Google Chrome")
        → "Iniciando Google Chrome."
    """
    frase = frase_aleatoria(contexto)
    if sufijo:
        # Quitar el punto final antes de añadir el sufijo
        if frase.endswith("."):
            frase = frase[:-1]
        texto = f"{frase} {sufijo}."
    else:
        texto = frase
    hablar(texto)