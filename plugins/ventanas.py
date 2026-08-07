"""
plugins/ventanas.py — Plugin de administración de ventanas del escritorio Linux (X11).

Responde a comandos como:
- "¿En qué programa estoy?" (VENTANA_ACTIVA)
- "¿Qué aplicaciones tengo abiertas?" (LISTAR_APLICACIONES)
- "Cierra Chrome" / "Cierra todas las terminales" (CERRAR_APP)
- "Trae Docker al frente" / "Enfoca VSCode" (ENFOCAR_APP)
- "Minimiza Chrome" (MINIMIZAR_APP)
- "Maximiza VSCode" (MAXIMIZAR_APP)
"""

import logging
from typing import Optional

import plugins
from modulos.gestor_aplicaciones import gestor_apps_sistema

logger = logging.getLogger("jarvis.plugins.ventanas")

INTENCIONES = [
    "VENTANA_ACTIVA",
    "LISTAR_APLICACIONES",
    "CERRAR_APP",
    "ENFOCAR_APP",
    "MINIMIZAR_APP",
    "MAXIMIZAR_APP",
    "CAMBIAR_VENTANA",
]


class PluginVentanas(plugins.BasePlugin):
    """Plugin para consultar y manipular ventanas activas del escritorio."""

    def __init__(self) -> None:
        super().__init__(
            nombre="ventanas",
            intenciones=INTENCIONES,
            descripcion="Administra y consulta las ventanas activas en el escritorio Linux.",
            categoria="Sistema",
        )

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        handlers = {
            "VENTANA_ACTIVA": self._ventana_activa,
            "LISTAR_APLICACIONES": self._listar_aplicaciones,
            "CERRAR_APP": self._cerrar_app,
            "ENFOCAR_APP": self._enfocar_app,
            "CAMBIAR_VENTANA": self._enfocar_app,
            "MINIMIZAR_APP": self._minimizar_app,
            "MAXIMIZAR_APP": self._maximizar_app,
        }
        handler = handlers.get(intencion)
        if handler:
            return handler(entidades, contexto)
        return "No reconocí la orden sobre ventanas."

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _ventana_activa(self, entidades: dict, contexto: dict) -> str:
        ventana = gestor_apps_sistema.obtener_ventana_activa()
        if not ventana:
            return "No pude determinar qué aplicación está activa."

        nombre_app = gestor_apps_sistema.obtener_nombre_amigable_app(ventana)
        return f"Estás trabajando en {nombre_app}."

    def _listar_aplicaciones(self, entidades: dict, contexto: dict) -> str:
        apps = gestor_apps_sistema.listar_nombres_aplicaciones_abiertas()
        if not apps:
            return "No hay aplicaciones gráficas abiertas en este momento."

        if len(apps) == 1:
            return f"Tienes abierta únicamente la aplicación: {apps[0]}."

        lista_str = ", ".join(apps[:-1]) + f" y {apps[-1]}"
        return f"Las aplicaciones que tienes abiertas son: {lista_str}."

    def _cerrar_app(self, entidades: dict, contexto: dict) -> str:
        nombre_app = entidades.get("app", "").strip()

        if not nombre_app:
            return "¿Qué aplicación deseas cerrar?"

        if "terminal" in nombre_app.lower():
            ok, msg = gestor_apps_sistema.cerrar_todas_las_terminales()
            return msg

        ok, msg = gestor_apps_sistema.cerrar_aplicacion(nombre_app)
        if not ok and ("no encontr" in msg.lower() or "ninguna" in msg.lower()):
            return f"{nombre_app} no está ejecutándose."
        return msg

    def _enfocar_app(self, entidades: dict, contexto: dict) -> str:
        nombre_app = entidades.get("app", "").strip()

        if not nombre_app:
            return "¿Qué aplicación deseas enfocar?"

        v = gestor_apps_sistema.buscar_ventana(nombre_app)
        if v:
            ok = gestor_apps_sistema.enfocar_ventana(v.window_id)
            if ok:
                nombre_amigable = gestor_apps_sistema.obtener_nombre_amigable_app(v.to_dict())
                return f"Cambiando a {nombre_amigable}."

        ok, msg = gestor_apps_sistema.abrir_aplicacion(nombre_app)
        return msg

    def _minimizar_app(self, entidades: dict, contexto: dict) -> str:
        nombre_app = entidades.get("app", "").strip()
        if not nombre_app:
            return "¿Qué ventana deseas minimizar?"

        ok, msg = gestor_apps_sistema.minimizar_aplicacion(nombre_app)
        return msg

    def _maximizar_app(self, entidades: dict, contexto: dict) -> str:
        nombre_app = entidades.get("app", "").strip()
        if not nombre_app:
            return "¿Qué ventana deseas maximizar?"

        ok, msg = gestor_apps_sistema.maximizar_aplicacion(nombre_app)
        return msg


# Registro automático
plugins.registrar(PluginVentanas())
