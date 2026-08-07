"""
interfaz/ventana_principal.py — Ventana widget principal de Jarvis.

Implementa la ventana flotante del asistente:
- Transparencia con soporte Wayland/GNOME
- Modo widget (compacto) y modo completo
- Posicionamiento recordado
- Arrastrable por el usuario
- System tray icon
- CSS theming completo con variables de paleta

Se conecta al EventBus para sincronizar con el cerebro real de Jarvis.
"""

import logging
import os
import json
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio

from interfaz.nucleo_visual import NucleoVisual
from interfaz.panel_estado import PanelEstado, PanelHistorial
from eventos.bus import bus, Eventos
from temas.gestor_temas import gestor_temas

logger = logging.getLogger("jarvis.interfaz.ventana")

# Ruta para guardar configuración de posición/tamaño
CONFIG_UI_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "datos", "ui_config.json")


class VentanaJarvis(Gtk.ApplicationWindow):
    """
    Ventana principal flotante del asistente Jarvis.

    Características:
    - Transparencia real con GTK4 + compositor GNOME
    - Modo WIDGET (pequeño, solo núcleo) y COMPLETO (panel estado)
    - Arrastrable, posición recordada
    - CSS theming con variables de paleta intercambiable
    - Integración total con EventBus (estado en tiempo real)
    """

    # Dimensiones
    WIDGET_W, WIDGET_H = 300, 420
    WIDGET_MIN_W, WIDGET_MIN_H = 280, 380

    def __init__(self, app: Gtk.Application, modo_demo: bool = False) -> None:
        super().__init__(application=app)

        self._modo_demo = modo_demo
        self._modo_completo = True
        self._arrastrando = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._pasos_macro_activos: list = []

        # Configurar ventana
        self._configurar_ventana()

        # Construir UI
        self._construir_ui()

        # Cargar CSS
        self._cargar_css()

        # Restaurar posición
        self._restaurar_posicion()

        # Conectar EventBus
        self._conectar_eventos()

        # En modo demo, iniciar ciclo de demostración
        if self._modo_demo:
            GLib.timeout_add(1500, self._ciclo_demo)
            self._demo_estados = [
                "reposo", "despertando", "escuchando", "procesando",
                "ejecutando", "hablando", "exito", "error", "esperando", "reposo"
            ]
            self._demo_idx = 0
            self._demo_textos = {
                "reposo":      ("", "", "Esperando activación..."),
                "despertando": ("", "", "¡Wake word detectada!"),
                "escuchando":  ("Jarvis, abre mi integrador", "", "Escuchando tu comando..."),
                "procesando":  ("abre mi integrador", "ABRIR_INTEGRADOR (100%)", "Analizando con NLP..."),
                "ejecutando":  ("abre mi integrador", "ABRIR_INTEGRADOR", "Ejecutando macro..."),
                "hablando":    ("", "", "Iniciando entorno de desarrollo..."),
                "exito":       ("", "", "¡Entorno listo!"),
                "error":       ("", "", "Error en ejecución"),
                "esperando":   ("", "", "Esperando confirmación..."),
            }

        logger.info("VentanaJarvis inicializada.")

    def _configurar_ventana(self) -> None:
        """Configura propiedades base de la ventana."""
        self.set_title("JARVIS")
        self.set_decorated(False)           # Sin decoración de sistema
        self.set_resizable(True)
        self.set_default_size(self.WIDGET_W, self.WIDGET_H)
        self.set_size_request(self.WIDGET_MIN_W, self.WIDGET_MIN_H)

        # Mantener siempre visible sobre otras ventanas
        # (funciona en muchos compositores Wayland/X11)
        # self.set_keep_above(True)  # Solo en X11/algunos compositors

        # Transparencia: necesita RGBA visual
        display = Gdk.Display.get_default()
        if display:
            self.set_opacity(0.97)

    def _construir_ui(self) -> None:
        """Construye todos los widgets de la interfaz."""

        # ── Contenedor raíz con CSS ──────────────────────────────────────────
        self._root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._root.set_name("jarvis-root")
        self.set_child(self._root)

        # ── Barra de título personalizada ────────────────────────────────────
        self._barra_titulo = self._construir_barra_titulo()
        self._root.append(self._barra_titulo)

        # ── Cuerpo principal ─────────────────────────────────────────────────
        self._cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._cuerpo.set_name("jarvis-cuerpo")
        self._root.append(self._cuerpo)

        # ── Núcleo visual animado ─────────────────────────────────────────────
        self._nucleo = NucleoVisual()
        self._nucleo.set_name("nucleo-visual")
        self._nucleo.set_halign(Gtk.Align.CENTER)
        self._nucleo.set_margin_top(12)
        self._nucleo.set_margin_bottom(8)
        self._cuerpo.append(self._nucleo)

        # ── Texto de estado grande ────────────────────────────────────────────
        self._lbl_estado_grande = Gtk.Label(label="J A R V I S")
        self._lbl_estado_grande.set_name("lbl-titulo-jarvis")
        self._lbl_estado_grande.set_halign(Gtk.Align.CENTER)
        self._cuerpo.append(self._lbl_estado_grande)

        # ── Separador ────────────────────────────────────────────────────────
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_name("separador-principal")
        sep.set_margin_start(16)
        sep.set_margin_end(16)
        sep.set_margin_top(8)
        sep.set_margin_bottom(4)
        self._cuerpo.append(sep)

        # ── Panel de estado ───────────────────────────────────────────────────
        self._panel_estado = PanelEstado()
        self._cuerpo.append(self._panel_estado)

        # ── Panel de historial (colapsable) ───────────────────────────────────
        self._revealer_historial = Gtk.Revealer()
        self._revealer_historial.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._revealer_historial.set_reveal_child(False)

        self._panel_historial = PanelHistorial()
        self._revealer_historial.set_child(self._panel_historial)
        self._cuerpo.append(self._revealer_historial)

        # ── Barra inferior ────────────────────────────────────────────────────
        self._barra_inferior = self._construir_barra_inferior()
        self._root.append(self._barra_inferior)

        # ── Gestos para arrastrar ─────────────────────────────────────────────
        self._configurar_arrastre()

    def _construir_barra_titulo(self) -> Gtk.Box:
        """Construye la barra de título personalizada."""
        barra = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        barra.set_name("barra-titulo")
        barra.set_margin_start(12)
        barra.set_margin_end(8)
        barra.set_margin_top(8)
        barra.set_margin_bottom(4)

        # Dot de estado compacto
        self._dot_titulo = Gtk.Label(label="●")
        self._dot_titulo.set_name("dot-titulo")
        barra.append(self._dot_titulo)

        # Título
        lbl_titulo = Gtk.Label(label="J A R V I S")
        lbl_titulo.set_name("lbl-barra-titulo")
        lbl_titulo.set_hexpand(True)
        lbl_titulo.set_halign(Gtk.Align.START)
        barra.append(lbl_titulo)

        # Botón configuración
        btn_config = Gtk.Button()
        btn_config.set_name("btn-barra")
        btn_config.set_icon_name("preferences-system-symbolic")
        btn_config.set_tooltip_text("Configuración")
        btn_config.connect("clicked", self._on_config_clicked)
        barra.append(btn_config)

        # Botón minimizar
        btn_min = Gtk.Button()
        btn_min.set_name("btn-barra")
        btn_min.set_icon_name("window-minimize-symbolic")
        btn_min.set_tooltip_text("Minimizar")
        btn_min.connect("clicked", lambda b: self.minimize())
        barra.append(btn_min)

        # Botón cerrar
        btn_cerrar = Gtk.Button()
        btn_cerrar.set_name("btn-barra-cerrar")
        btn_cerrar.set_icon_name("window-close-symbolic")
        btn_cerrar.set_tooltip_text("Cerrar")
        btn_cerrar.connect("clicked", lambda b: self.close())
        barra.append(btn_cerrar)

        return barra

    def _construir_barra_inferior(self) -> Gtk.Box:
        """Construye la barra inferior con controles."""
        barra = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        barra.set_name("barra-inferior")
        barra.set_margin_start(12)
        barra.set_margin_end(12)
        barra.set_margin_top(4)
        barra.set_margin_bottom(10)

        # Botón historial
        btn_historial = Gtk.ToggleButton(label="Historial")
        btn_historial.set_name("btn-inferior")
        btn_historial.connect("toggled", self._on_historial_toggled)
        barra.append(btn_historial)

        # Separador flexible
        barra.set_hexpand(True)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        barra.append(spacer)

        # Indicador de micrófono
        self._lbl_mic = Gtk.Label(label="🎤")
        self._lbl_mic.set_name("lbl-mic")
        self._lbl_mic.set_tooltip_text("Micrófono activo")
        barra.append(self._lbl_mic)

        return barra

    def _configurar_arrastre(self) -> None:
        """Configura el gesto de arrastre para mover la ventana."""
        gesto_drag = Gtk.GestureDrag()
        gesto_drag.set_button(1)  # Botón izquierdo
        gesto_drag.connect("drag-begin", self._on_drag_begin)
        gesto_drag.connect("drag-update", self._on_drag_update)
        gesto_drag.connect("drag-end", self._on_drag_end)
        self._barra_titulo.add_controller(gesto_drag)

    def _on_drag_begin(self, gesture, start_x, start_y) -> None:
        """Inicio de arrastre."""
        self._arrastrando = True

    def _on_drag_update(self, gesture, offset_x, offset_y) -> None:
        """Actualización de arrastre — mueve la ventana."""
        # En Wayland no podemos obtener posición exacta, pero usamos begin_move_drag
        if self._arrastrando:
            surface = self.get_surface()
            if hasattr(surface, 'begin_move_drag'):
                # X11 method
                try:
                    surface.begin_move_drag(1, int(offset_x), int(offset_y), 0)
                except Exception:
                    pass

    def _on_drag_end(self, gesture, offset_x, offset_y) -> None:
        """Fin de arrastre — guarda posición."""
        self._arrastrando = False
        self._guardar_posicion()

    def _cargar_css(self) -> None:
        """Carga el CSS de la interfaz con las variables de la paleta activa."""
        paleta = gestor_temas.obtener_paleta()
        css = self._generar_css(paleta)

        provider = Gtk.CssProvider()
        provider.load_from_string(css)

        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        self._css_provider = provider
        logger.debug("CSS cargado con paleta: %s", paleta.nombre)

    def _generar_css(self, paleta) -> str:
        """Genera el CSS completo usando las variables de la paleta."""
        bg = paleta.BACKGROUND
        surface = paleta.SURFACE
        surface2 = paleta.SURFACE_2
        primary = paleta.PRIMARY
        secondary = paleta.SECONDARY
        accent = paleta.ACCENT
        text = paleta.TEXT
        text_dim = paleta.TEXT_DIM
        success = paleta.SUCCESS
        warning = paleta.WARNING
        error = paleta.ERROR
        border = paleta.BORDER
        border_active = paleta.BORDER_ACTIVE

        return f"""
/* ═══════════════════════════════════════════════════════════
   JARVIS — CSS Principal GTK4
   Paleta: {paleta.nombre}
   ═══════════════════════════════════════════════════════════ */

@import url("https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Share+Tech+Mono&display=swap");

/* ── Ventana raíz ─────────────────────────────────────────── */
window {{
    background-color: transparent;
}}

#jarvis-root {{
    background: linear-gradient(160deg, {surface} 0%, {bg} 100%);
    border-radius: 16px;
    border: 1px solid {border_active}44;
    box-shadow: 0 8px 32px {primary}22,
                0 0 0 1px {border}44;
}}

/* ── Barra de título ─────────────────────────────────────── */
#barra-titulo {{
    background: linear-gradient(90deg, {surface2} 0%, {surface} 100%);
    border-radius: 16px 16px 0 0;
    border-bottom: 1px solid {border_active}33;
    padding: 4px 6px;
}}

#lbl-barra-titulo {{
    font-family: 'Orbitron', 'Share Tech Mono', monospace;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 4px;
    color: {primary};
}}

#dot-titulo {{
    font-size: 10px;
    color: {primary};
}}

/* ── Botones de la barra ─────────────────────────────────── */
#btn-barra {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 2px;
    min-width: 22px;
    min-height: 22px;
    color: {text_dim};
    opacity: 0.7;
}}

#btn-barra:hover {{
    background: {border}66;
    color: {text};
    opacity: 1.0;
}}

#btn-barra-cerrar {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 2px;
    min-width: 22px;
    min-height: 22px;
    color: {text_dim};
    opacity: 0.7;
}}

#btn-barra-cerrar:hover {{
    background: {error}44;
    color: {error};
    opacity: 1.0;
}}

/* ── Cuerpo ──────────────────────────────────────────────── */
#jarvis-cuerpo {{
    padding: 0 0 4px 0;
}}

/* ── Título principal ────────────────────────────────────── */
#lbl-titulo-jarvis {{
    font-family: 'Orbitron', 'Share Tech Mono', monospace;
    font-size: 14px;
    font-weight: bold;
    letter-spacing: 8px;
    color: {primary};
    margin-top: 4px;
    margin-bottom: 8px;
}}

/* ── Panel de estado ─────────────────────────────────────── */
#panel-estado {{
    padding: 4px 0;
}}

#fila-estado {{
    margin-bottom: 4px;
}}

#lbl-estado {{
    font-family: 'Orbitron', 'Share Tech Mono', monospace;
    font-size: 11px;
    letter-spacing: 2px;
    color: {primary};
}}

#dot-estado {{
    font-size: 12px;
    color: {primary};
}}

/* ── Etiquetas de sección ────────────────────────────────── */
#lbl-seccion {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    letter-spacing: 2px;
    color: {text_dim};
    margin-top: 6px;
    margin-bottom: 1px;
}}

/* ── Texto de usuario ────────────────────────────────────── */
#lbl-texto-usuario {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    color: {text};
    font-style: italic;
}}

/* ── Intención NLP ───────────────────────────────────────── */
#lbl-intencion {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: {accent};
    letter-spacing: 1px;
}}

/* ── Acción ──────────────────────────────────────────────── */
#lbl-accion {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: {text_dim};
}}

/* ── Pasos de macro ──────────────────────────────────────── */
#lbl-paso {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: {text_dim};
}}

/* ── Separadores ─────────────────────────────────────────── */
#separador, #separador-principal {{
    background: {border}88;
    min-height: 1px;
}}

/* ── Barra inferior ──────────────────────────────────────── */
#barra-inferior {{
    background: {surface2};
    border-radius: 0 0 16px 16px;
    border-top: 1px solid {border}44;
    padding: 4px 8px;
}}

#btn-inferior {{
    background: {border}55;
    border: 1px solid {border};
    border-radius: 6px;
    padding: 2px 8px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    letter-spacing: 1px;
    color: {text_dim};
    min-height: 22px;
}}

#btn-inferior:hover {{
    background: {primary}22;
    border-color: {primary}66;
    color: {primary};
}}

#btn-inferior:checked {{
    background: {primary}33;
    border-color: {primary};
    color: {primary};
}}

#lbl-mic {{
    font-size: 14px;
    color: {text_dim};
    opacity: 0.6;
}}

/* ── Historial ───────────────────────────────────────────── */
#panel-historial {{
    padding: 4px 16px 8px 16px;
}}

#lbl-historial-hora {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    color: {text_dim};
    min-width: 35px;
}}

#lbl-historial-texto {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: {text_dim};
    opacity: 0.8;
}}

/* ── Scrollbar ───────────────────────────────────────────── */
scrollbar {{
    background: transparent;
    min-width: 4px;
}}

scrollbar slider {{
    background: {border_active}44;
    border-radius: 4px;
    min-width: 4px;
}}

scrollbar slider:hover {{
    background: {primary}88;
}}
"""

    def _conectar_eventos(self) -> None:
        """Suscribe los callbacks de la UI al EventBus."""
        # Configurar GLib para thread-safety
        bus.configurar_glib(GLib.idle_add)

        bus.suscribir(Eventos.REPOSO, self._on_reposo)
        bus.suscribir(Eventos.DESPERTANDO, self._on_despertando)
        bus.suscribir(Eventos.ESCUCHANDO, self._on_escuchando)
        bus.suscribir(Eventos.PROCESANDO, self._on_procesando)
        bus.suscribir(Eventos.INTENCION, self._on_intencion)
        bus.suscribir(Eventos.EJECUTANDO, self._on_ejecutando)
        bus.suscribir(Eventos.HABLANDO, self._on_hablando)
        bus.suscribir(Eventos.FIN_HABLA, self._on_fin_habla)
        bus.suscribir(Eventos.EXITO, self._on_exito)
        bus.suscribir(Eventos.ERROR, self._on_error)
        bus.suscribir(Eventos.ESPERANDO, self._on_esperando)
        bus.suscribir(Eventos.TEXTO_USUARIO, self._on_texto_usuario)
        bus.suscribir(Eventos.PROGRESO_MACRO, self._on_progreso_macro)
        bus.suscribir(Eventos.MACRO_INICIADA, self._on_macro_iniciada)
        bus.suscribir(Eventos.MACRO_COMPLETADA, self._on_macro_completada)
        bus.suscribir(Eventos.CAMBIO_TEMA, self._on_cambio_tema)
        bus.suscribir(Eventos.AUDIO_LEVEL, self._on_audio_level)
        bus.suscribir(Eventos.MICROPHONE_ACTIVE, self._on_microphone_active)
        bus.suscribir(Eventos.MICROPHONE_IDLE, self._on_microphone_idle)

        # Estado inicial: reposo
        self._aplicar_estado_ui("reposo")
        logger.info("EventBus conectado a la UI.")

    # ── Callbacks del EventBus ────────────────────────────────────────────────

    def _on_reposo(self, evento, datos):
        self._aplicar_estado_ui("reposo")
        self._panel_estado.limpiar()
        GLib.timeout_add(3000, self._ocultar_progreso_macro_delayed)

    def _on_despertando(self, evento, datos):
        self._aplicar_estado_ui("despertando")
        self._panel_estado.actualizar_accion("Wake word detectada...")

    def _on_escuchando(self, evento, datos):
        self._aplicar_estado_ui("escuchando")
        self._panel_estado.actualizar_accion("Escuchando tu comando...")
        self._lbl_mic.set_text("🎤")

    def _on_audio_level(self, evento, datos):
        nivel = datos.get("nivel", 0.0)
        self._nucleo.set_nivel_audio(float(nivel))

    def _on_microphone_active(self, evento, datos):
        self._lbl_mic.set_text("🎙️")
        self._lbl_mic.set_tooltip_text("Micrófono activo")

    def _on_microphone_idle(self, evento, datos):
        self._lbl_mic.set_text("🎤")
        self._lbl_mic.set_tooltip_text("Micrófono en espera")

    def _on_procesando(self, evento, datos):
        self._aplicar_estado_ui("procesando")
        texto = datos.get("texto", "")
        self._panel_estado.actualizar_accion(f"Analizando: {texto[:40]}")

    def _on_intencion(self, evento, datos):
        intencion = datos.get("intencion", "")
        confianza = datos.get("confianza", 0.0)
        self._panel_estado.actualizar_intencion(intencion, confianza)

    def _on_ejecutando(self, evento, datos):
        self._aplicar_estado_ui("ejecutando")
        desc = datos.get("descripcion", datos.get("accion", "Ejecutando..."))
        self._panel_estado.actualizar_accion(desc)

    def _on_hablando(self, evento, datos):
        self._aplicar_estado_ui("hablando")
        texto = datos.get("texto", "")
        self._panel_estado.actualizar_accion(f"Respondiendo: {texto[:50]}...")
        self._lbl_mic.set_text("🔊")

    def _on_fin_habla(self, evento, datos):
        self._lbl_mic.set_text("🎤")

    def _on_exito(self, evento, datos):
        self._aplicar_estado_ui("exito")
        resultado = datos.get("resultado", "Completado")
        self._panel_estado.actualizar_accion(str(resultado)[:60])
        # Volver a escuchando después de 2 segundos
        GLib.timeout_add(2000, lambda: self._aplicar_estado_ui("escuchando") or False)

    def _on_error(self, evento, datos):
        self._aplicar_estado_ui("error")
        mensaje = datos.get("mensaje", "Error desconocido")
        self._panel_estado.actualizar_accion(f"Error: {str(mensaje)[:50]}")
        GLib.timeout_add(3000, lambda: self._aplicar_estado_ui("escuchando") or False)

    def _on_esperando(self, evento, datos):
        self._aplicar_estado_ui("esperando")
        self._panel_estado.actualizar_accion("Esperando confirmación...")

    def _on_texto_usuario(self, evento, datos):
        texto = datos.get("texto", "")
        self._panel_estado.actualizar_texto_usuario(texto)
        # Agregar al historial
        intencion = datos.get("intencion", "")
        self._panel_historial.agregar_entrada(texto, intencion)

    def _on_progreso_macro(self, evento, datos):
        paso = datos.get("paso", "")
        ok = datos.get("ok", None)
        desc = datos.get("descripcion", "")

        # Actualizar o agregar paso
        encontrado = False
        for p in self._pasos_macro_activos:
            if p["nombre"] == paso:
                p["estado"] = "ok" if ok else "error" if ok is False else "ejecutando"
                encontrado = True
                break

        if not encontrado:
            self._pasos_macro_activos.append({
                "nombre": paso,
                "estado": "ejecutando" if ok is None else ("ok" if ok else "error")
            })

        self._panel_estado.mostrar_progreso_macro(self._pasos_macro_activos)

    def _on_macro_iniciada(self, evento, datos):
        intencion = datos.get("intencion", "")
        self._pasos_macro_activos = []
        if intencion == "ABRIR_INTEGRADOR":
            for nombre in ["Proyecto", "Editor", "Docker", "Chrome", "Tilix/Vite"]:
                self._pasos_macro_activos.append({"nombre": nombre, "estado": "pendiente"})
        self._panel_estado.mostrar_progreso_macro(self._pasos_macro_activos)

    def _on_macro_completada(self, evento, datos):
        exito = datos.get("exito", True)
        if exito:
            for p in self._pasos_macro_activos:
                if p["estado"] != "error":
                    p["estado"] = "ok"
            self._panel_estado.mostrar_progreso_macro(self._pasos_macro_activos)

    def _on_cambio_tema(self, evento, datos):
        nombre_tema = datos.get("nombre_tema", "")
        paleta = gestor_temas.obtener_paleta()
        css = self._generar_css(paleta)
        self._css_provider.load_from_string(css)
        self._nucleo.actualizar_paleta()
        logger.info("Tema actualizado en UI: %s", nombre_tema)

    # ── Aplicación de estado ──────────────────────────────────────────────────

    def _aplicar_estado_ui(self, estado: str) -> None:
        """Aplica el estado visual completo a todos los widgets."""
        self._nucleo.set_estado(estado)
        self._panel_estado.actualizar_estado(estado)

        # Actualizar dot del título
        colores = {
            "reposo":      "#6B8AAA",
            "despertando": "#00CFFF",
            "escuchando":  "#00CFFF",
            "procesando":  "#0088FF",
            "ejecutando":  "#00FFEE",
            "hablando":    "#00CFFF",
            "exito":       "#00FF9D",
            "error":       "#FF3D71",
            "esperando":   "#FFB800",
        }
        color = colores.get(estado, "#6B8AAA")
        self._dot_titulo.set_markup(f'<span foreground="{color}">●</span>')

    def _ocultar_progreso_macro_delayed(self) -> bool:
        """Oculta el progreso de macro con delay."""
        self._pasos_macro_activos = []
        self._panel_estado.ocultar_progreso_macro()
        return False

    # ── Controles ─────────────────────────────────────────────────────────────

    def _on_historial_toggled(self, btn: Gtk.ToggleButton) -> None:
        """Muestra/oculta el panel de historial."""
        self._revealer_historial.set_reveal_child(btn.get_active())

    def _on_config_clicked(self, btn) -> None:
        """Abre el diálogo de configuración."""
        self._mostrar_dialogo_config()

    def _mostrar_dialogo_config(self) -> None:
        """Muestra el diálogo de configuración de Jarvis."""
        dialog = Gtk.Dialog(title="Configuración — JARVIS", transient_for=self, modal=True)
        dialog.set_default_size(360, 400)

        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        # Selección de tema
        lbl_tema = Gtk.Label(label="Paleta de colores:")
        lbl_tema.set_halign(Gtk.Align.START)
        box.append(lbl_tema)

        combo_temas = Gtk.ComboBoxText()
        for nombre_tema in gestor_temas.listar_temas():
            combo_temas.append_text(nombre_tema)
        combo_temas.set_active(
            gestor_temas.listar_temas().index(gestor_temas.obtener_nombre())
        )
        combo_temas.connect("changed", self._on_tema_changed)
        box.append(combo_temas)

        # Botón cerrar
        btn_cerrar = Gtk.Button(label="Cerrar")
        btn_cerrar.connect("clicked", lambda b: dialog.close())
        box.append(btn_cerrar)

        dialog.present()

    def _on_tema_changed(self, combo) -> None:
        """Cambia el tema desde el diálogo de configuración."""
        nombre = combo.get_active_text()
        if nombre:
            gestor_temas.cambiar_tema(nombre)

    # ── Persistencia de posición ──────────────────────────────────────────────

    def _guardar_posicion(self) -> None:
        """Guarda la configuración de UI."""
        try:
            w, h = self.get_default_size()
            config = {"width": w, "height": h}
            os.makedirs(os.path.dirname(CONFIG_UI_PATH), exist_ok=True)
            with open(CONFIG_UI_PATH, "w") as f:
                json.dump(config, f)
        except Exception as e:
            logger.debug("No se pudo guardar posición: %s", e)

    def _restaurar_posicion(self) -> None:
        """Restaura la configuración de UI guardada."""
        try:
            if os.path.exists(CONFIG_UI_PATH):
                with open(CONFIG_UI_PATH) as f:
                    config = json.load(f)
                w = config.get("width", self.WIDGET_W)
                h = config.get("height", self.WIDGET_H)
                self.set_default_size(w, h)
        except Exception as e:
            logger.debug("No se pudo restaurar posición: %s", e)

    # ── Modo Demo ─────────────────────────────────────────────────────────────

    def _ciclo_demo(self) -> bool:
        """Cicla por todos los estados en modo demo."""
        if self._demo_idx >= len(self._demo_estados):
            self._demo_idx = 0

        estado = self._demo_estados[self._demo_idx]
        self._aplicar_estado_ui(estado)

        textos = self._demo_textos.get(estado, ("", "", ""))
        if textos[0]:
            self._panel_estado.actualizar_texto_usuario(textos[0])
        if textos[1]:
            self._panel_estado.actualizar_intencion(textos[1].split()[0], 100.0)
        if textos[2]:
            self._panel_estado.actualizar_accion(textos[2])

        self._demo_idx += 1
        return True  # Continuar timer


class AppJarvis(Gtk.Application):
    """
    Aplicación GTK4 de Jarvis.

    Gestiona el ciclo de vida de la ventana principal.
    """

    def __init__(self, modo_demo: bool = False) -> None:
        super().__init__(application_id="com.jarvis.desktop",
                        flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._modo_demo = modo_demo
        self._ventana: VentanaJarvis = None

    def do_activate(self) -> None:
        """Crea y presenta la ventana principal."""
        if not self._ventana:
            self._ventana = VentanaJarvis(self, modo_demo=self._modo_demo)

        self._ventana.present()

    def obtener_ventana(self) -> VentanaJarvis:
        """Devuelve la referencia a la ventana principal."""
        return self._ventana
