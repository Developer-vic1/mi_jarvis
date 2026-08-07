"""
plugins/datetime_info.py — Plugin de información de fecha y hora.

Responde preguntas sobre:
- Hora actual
- Fecha de hoy
- Día de la semana
- Mes actual
- Año actual
"""

import logging
from datetime import datetime

import plugins

logger = logging.getLogger("jarvis.datetime")

DIAS_SEMANA = [
    "lunes", "martes", "miércoles", "jueves",
    "viernes", "sábado", "domingo",
]

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class PluginDateTime(plugins.BasePlugin):
    """Plugin de información temporal: hora, fecha, día, mes y año."""

    def __init__(self) -> None:
        super().__init__(
            nombre="datetime",
            intenciones=["HORA", "FECHA", "DIA_SEMANA", "MES", "AÑO"],
            descripcion="Informa la hora, fecha, día de la semana, mes y año actuales.",
            categoria="Información",
        )

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        ahora = datetime.now()

        if intencion == "HORA":
            hora_12 = ahora.strftime("%I:%M %p").lstrip("0")
            return f"Son las {hora_12}."

        elif intencion == "FECHA":
            dia = ahora.day
            mes = MESES[ahora.month - 1]
            año = ahora.year
            return f"Hoy es {dia} de {mes} de {año}."

        elif intencion == "DIA_SEMANA":
            dia_semana = DIAS_SEMANA[ahora.weekday()]
            return f"Hoy es {dia_semana}."

        elif intencion == "MES":
            mes = MESES[ahora.month - 1]
            return f"Estamos en {mes}."

        elif intencion == "AÑO":
            return f"Estamos en el año {ahora.year}."

        return "No pude obtener la información de fecha."


plugins.registrar(PluginDateTime())
