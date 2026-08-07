"""
interfaz/panel_estado.py — Panel de estado y texto de Jarvis.

Muestra el estado actual, el texto reconocido, la intención NLP detectada
y la acción en ejecución. Se actualiza en tiempo real mediante el EventBus.
"""

import logging
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Pango

logger = logging.getLogger("jarvis.interfaz.panel_estado")


class PanelEstado(Gtk.Box):
    """
    Panel vertical con información de estado en tiempo real.

    Secciones:
    - Indicador visual de estado (texto + icono)
    - Texto que dijo el usuario
    - Intención NLP detectada
    - Acción en ejecución / resultado
    - Progreso de macro (barras de progreso)
    """

    ICONOS_ESTADO = {
        "reposo":       ("😴", "REPOSO"),
        "despertando":  ("⚡", "DESPERTANDO"),
        "escuchando":   ("👂", "ESCUCHANDO"),
        "procesando":   ("🧠", "PROCESANDO"),
        "ejecutando":   ("⚙️", "EJECUTANDO"),
        "hablando":     ("🔊", "HABLANDO"),
        "exito":        ("✓", "ÉXITO"),
        "error":        ("✗", "ERROR"),
        "esperando":    ("⏳", "ESPERANDO"),
    }

    COLORES_ESTADO = {
        "reposo":       "#6B8AAA",
        "despertando":  "#00CFFF",
        "escuchando":   "#00CFFF",
        "procesando":   "#0088FF",
        "ejecutando":   "#00FFEE",
        "hablando":     "#00CFFF",
        "exito":        "#00FF9D",
        "error":        "#FF3D71",
        "esperando":    "#FFB800",
    }

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_name("panel-estado")

        self._estado_actual = "reposo"
        self._pasos_macro: dict = {}

        self._construir_ui()

    def _construir_ui(self) -> None:
        """Construye todos los widgets del panel."""
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        # ── Fila de estado ───────────────────────────────────────────────────
        fila_estado = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        fila_estado.set_name("fila-estado")

        self._dot_estado = Gtk.Label(label="●")
        self._dot_estado.set_name("dot-estado")

        self._lbl_estado = Gtk.Label(label="REPOSO")
        self._lbl_estado.set_name("lbl-estado")
        self._lbl_estado.set_halign(Gtk.Align.START)

        fila_estado.append(self._dot_estado)
        fila_estado.append(self._lbl_estado)
        self.append(fila_estado)

        # ── Separador ────────────────────────────────────────────────────────
        sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep1.set_name("separador")
        self.append(sep1)

        # ── Texto del usuario ────────────────────────────────────────────────
        self._lbl_usuario_label = Gtk.Label(label="USUARIO")
        self._lbl_usuario_label.set_name("lbl-seccion")
        self._lbl_usuario_label.set_halign(Gtk.Align.START)
        self.append(self._lbl_usuario_label)

        self._lbl_texto_usuario = Gtk.Label(label="—")
        self._lbl_texto_usuario.set_name("lbl-texto-usuario")
        self._lbl_texto_usuario.set_halign(Gtk.Align.START)
        self._lbl_texto_usuario.set_wrap(True)
        self._lbl_texto_usuario.set_max_width_chars(30)
        self._lbl_texto_usuario.set_ellipsize(Pango.EllipsizeMode.END)
        self.append(self._lbl_texto_usuario)

        # ── Intención NLP ────────────────────────────────────────────────────
        self._lbl_nlp_label = Gtk.Label(label="NLP →")
        self._lbl_nlp_label.set_name("lbl-seccion")
        self._lbl_nlp_label.set_halign(Gtk.Align.START)
        self.append(self._lbl_nlp_label)

        self._lbl_intencion = Gtk.Label(label="—")
        self._lbl_intencion.set_name("lbl-intencion")
        self._lbl_intencion.set_halign(Gtk.Align.START)
        self.append(self._lbl_intencion)

        # ── Acción/Resultado ─────────────────────────────────────────────────
        self._lbl_accion_label = Gtk.Label(label="ACCIÓN")
        self._lbl_accion_label.set_name("lbl-seccion")
        self._lbl_accion_label.set_halign(Gtk.Align.START)
        self.append(self._lbl_accion_label)

        self._lbl_accion = Gtk.Label(label="—")
        self._lbl_accion.set_name("lbl-accion")
        self._lbl_accion.set_halign(Gtk.Align.START)
        self._lbl_accion.set_wrap(True)
        self._lbl_accion.set_max_width_chars(30)
        self.append(self._lbl_accion)

        # ── Progreso de macro ────────────────────────────────────────────────
        self._box_macro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._box_macro.set_name("box-macro")
        self._box_macro.set_visible(False)
        self.append(self._box_macro)

        self._lbl_macro_titulo = Gtk.Label(label="PROGRESO")
        self._lbl_macro_titulo.set_name("lbl-seccion")
        self._lbl_macro_titulo.set_halign(Gtk.Align.START)
        self._box_macro.append(self._lbl_macro_titulo)

        self._box_pasos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._box_macro.append(self._box_pasos)

    def actualizar_estado(self, estado: str) -> None:
        """
        Actualiza el indicador de estado.

        Args:
            estado: Nombre del estado (e.g. 'escuchando').
        """
        self._estado_actual = estado
        icono, texto = self.ICONOS_ESTADO.get(estado, ("●", estado.upper()))

        try:
            from temas.gestor_temas import gestor_temas
            paleta = gestor_temas.obtener_paleta()
            colores = {
                "reposo":       paleta.TEXT_DIM,
                "despertando":  paleta.PRIMARY,
                "escuchando":   paleta.PRIMARY,
                "procesando":   paleta.SECONDARY,
                "ejecutando":   paleta.ACCENT,
                "hablando":     paleta.PRIMARY,
                "exito":        paleta.SUCCESS,
                "error":        paleta.ERROR,
                "esperando":    paleta.WARNING,
            }
            color = colores.get(estado, paleta.PRIMARY)
        except Exception:
            color = self.COLORES_ESTADO.get(estado, "#6B8AAA")

        self._dot_estado.set_markup(f'<span foreground="{color}" size="large">●</span>')
        self._lbl_estado.set_markup(f'<span foreground="{color}" font_weight="bold">{texto}</span>')

    def actualizar_texto_usuario(self, texto: str) -> None:
        """Actualiza el texto reconocido del usuario."""
        if texto:
            self._lbl_texto_usuario.set_markup(f'<span style="italic">"{texto}"</span>')
        else:
            self._lbl_texto_usuario.set_text("—")

    def actualizar_intencion(self, intencion: str, confianza: float = 0.0) -> None:
        """Actualiza la intención NLP detectada."""
        if intencion and intencion != "DESCONOCIDO":
            conf_str = f" ({confianza:.0f}%)" if confianza > 0 else ""
            try:
                from temas.gestor_temas import gestor_temas
                color_accent = gestor_temas.obtener_paleta().ACCENT
            except Exception:
                color_accent = "#00FFEE"
            self._lbl_intencion.set_markup(
                f'<span font_family="monospace" foreground="{color_accent}">{intencion}{conf_str}</span>'
            )
        else:
            self._lbl_intencion.set_text("—")

    def actualizar_accion(self, descripcion: str) -> None:
        """Actualiza la descripción de la acción en curso."""
        if descripcion:
            self._lbl_accion.set_text(descripcion)
        else:
            self._lbl_accion.set_text("—")

    def mostrar_progreso_macro(self, pasos: list) -> None:
        """
        Muestra los pasos de progreso de una macro.

        Args:
            pasos: Lista de dicts con {nombre, estado} donde estado es
                   'pendiente', 'ejecutando', 'ok', 'error'.
        """
        self._box_macro.set_visible(True)

        # Limpiar pasos anteriores
        hijo = self._box_pasos.get_first_child()
        while hijo:
            siguiente = hijo.get_next_sibling()
            self._box_pasos.remove(hijo)
            hijo = siguiente

        iconos = {
            "pendiente":  ("·", "#6B8AAA"),
            "ejecutando": ("→", "#FFB800"),
            "ok":         ("✓", "#00FF9D"),
            "error":      ("✗", "#FF3D71"),
        }

        for paso in pasos:
            nombre = paso.get("nombre", "")
            estado_paso = paso.get("estado", "pendiente")
            icono_p, color_p = iconos.get(estado_paso, ("·", "#6B8AAA"))

            fila = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            lbl_icono = Gtk.Label()
            lbl_icono.set_markup(f'<span foreground="{color_p}">{icono_p}</span>')
            lbl_nombre = Gtk.Label(label=nombre)
            lbl_nombre.set_name("lbl-paso")
            lbl_nombre.set_halign(Gtk.Align.START)
            fila.append(lbl_icono)
            fila.append(lbl_nombre)
            self._box_pasos.append(fila)

    def ocultar_progreso_macro(self) -> None:
        """Oculta el panel de progreso de macro."""
        self._box_macro.set_visible(False)

    def limpiar(self) -> None:
        """Limpia todos los campos de texto."""
        self._lbl_texto_usuario.set_text("—")
        self._lbl_intencion.set_text("—")
        self._lbl_accion.set_text("—")
        self.ocultar_progreso_macro()


class PanelHistorial(Gtk.Box):
    """
    Panel de historial de interacciones recientes.
    """

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_name("panel-historial")
        self._entradas: list = []
        self._max_entradas = 8
        self._construir_ui()

    def _construir_ui(self) -> None:
        self.set_margin_start(16)
        self.set_margin_end(16)

        lbl_titulo = Gtk.Label(label="HISTORIAL")
        lbl_titulo.set_name("lbl-seccion")
        lbl_titulo.set_halign(Gtk.Align.START)
        self.append(lbl_titulo)

        # ScrolledWindow para el historial
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(120)
        scroll.set_propagate_natural_height(True)
        self.append(scroll)

        self._box_entradas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scroll.set_child(self._box_entradas)

    def agregar_entrada(self, texto: str, intencion: str) -> None:
        """Agrega una nueva entrada al historial."""
        import datetime
        hora = datetime.datetime.now().strftime("%H:%M")

        # Crear fila
        fila = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_hora = Gtk.Label(label=hora)
        lbl_hora.set_name("lbl-historial-hora")
        lbl_texto = Gtk.Label(label=texto[:35] + "…" if len(texto) > 35 else texto)
        lbl_texto.set_name("lbl-historial-texto")
        lbl_texto.set_halign(Gtk.Align.START)
        fila.append(lbl_hora)
        fila.append(lbl_texto)

        self._box_entradas.prepend(fila)
        self._entradas.insert(0, fila)

        # Mantener máximo
        while len(self._entradas) > self._max_entradas:
            viejo = self._entradas.pop()
            self._box_entradas.remove(viejo)
