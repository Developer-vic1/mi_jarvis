"""
temas/gestor_temas.py — Gestor centralizado de paletas de color para Jarvis.

Implementa el sistema de temas: cada paleta define variables de color que la
interfaz consume. NO se escriben colores directamente en los módulos de UI.

La paleta activa puede cambiarse en tiempo de ejecución mediante cambio_tema().
La configuración se persiste usando la memoria de Jarvis (preferencias SQLite).
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger("jarvis.temas")


@dataclass
class Paleta:
    """
    Paleta de colores completa para la interfaz de Jarvis.

    Todos los campos son strings hexadecimales con formato "#RRGGBB" o "rgba(r,g,b,a)".
    La UI SIEMPRE consume variables de esta paleta, nunca colores directos.
    """
    nombre: str
    descripcion: str

    # ── Colores principales ───────────────────────────────────────────────────
    PRIMARY: str        # Color principal: núcleo activo, acentos, escuchando
    SECONDARY: str      # Color secundario: procesamiento, pensando
    ACCENT: str         # Acento: botones activos, selecciones

    # ── Fondos y superficies ──────────────────────────────────────────────────
    BACKGROUND: str     # Fondo general de la ventana
    SURFACE: str        # Superficie de paneles, cards
    SURFACE_2: str      # Segunda superficie (más clara)

    # ── Texto ─────────────────────────────────────────────────────────────────
    TEXT: str           # Texto principal
    TEXT_DIM: str       # Texto secundario/atenuado
    TEXT_ACCENT: str    # Texto de acento (sobre color PRIMARY)

    # ── Estados semánticos ────────────────────────────────────────────────────
    SUCCESS: str        # Verde éxito
    WARNING: str        # Ámbar advertencia/espera
    ERROR: str          # Rojo error

    # ── Efectos visuales del núcleo ───────────────────────────────────────────
    GLOW: str           # Resplandor del núcleo (rgba con alpha)
    GLOW_2: str         # Resplandor secundario
    PARTICLE: str       # Color de partículas
    PARTICLE_DIM: str   # Partículas atenuadas
    WAVEFORM: str       # Forma de onda del habla

    # ── Bordes y separadores ──────────────────────────────────────────────────
    BORDER: str         # Borde del widget
    BORDER_ACTIVE: str  # Borde cuando está activo

    @property
    def background(self) -> str:
        return self.BACKGROUND

    @property
    def surface(self) -> str:
        return self.SURFACE

    @property
    def primary(self) -> str:
        return self.PRIMARY

    @property
    def secondary(self) -> str:
        return self.SECONDARY

    @property
    def accent(self) -> str:
        return self.ACCENT

    @property
    def text(self) -> str:
        return self.TEXT

    @property
    def muted(self) -> str:
        return self.TEXT_DIM

    @property
    def success(self) -> str:
        return self.SUCCESS

    @property
    def warning(self) -> str:
        return self.WARNING

    @property
    def error(self) -> str:
        return self.ERROR

    # ── Semántica de estados → usa colores de la paleta ──────────────────────
    @property
    def color_reposo(self) -> str:
        return self.GLOW

    @property
    def color_escuchando(self) -> str:
        return self.PRIMARY

    @property
    def color_procesando(self) -> str:
        return self.SECONDARY

    @property
    def color_ejecutando(self) -> str:
        return self.ACCENT

    @property
    def color_hablando(self) -> str:
        return self.PRIMARY

    @property
    def color_exito(self) -> str:
        return self.SUCCESS

    @property
    def color_error(self) -> str:
        return self.ERROR

    @property
    def color_esperando(self) -> str:
        return self.WARNING

    def to_css_variables(self) -> str:
        """
        Genera las variables CSS para inyectar en GTK4.

        Returns:
            String con definiciones CSS de variables (custom properties).
        """
        return f"""
            --jarvis-primary: {self.PRIMARY};
            --jarvis-secondary: {self.SECONDARY};
            --jarvis-accent: {self.ACCENT};
            --jarvis-background: {self.BACKGROUND};
            --jarvis-surface: {self.SURFACE};
            --jarvis-surface-2: {self.SURFACE_2};
            --jarvis-text: {self.TEXT};
            --jarvis-text-dim: {self.TEXT_DIM};
            --jarvis-text-accent: {self.TEXT_ACCENT};
            --jarvis-success: {self.SUCCESS};
            --jarvis-warning: {self.WARNING};
            --jarvis-error: {self.ERROR};
            --jarvis-glow: {self.GLOW};
            --jarvis-glow-2: {self.GLOW_2};
            --jarvis-particle: {self.PARTICLE};
            --jarvis-particle-dim: {self.PARTICLE_DIM};
            --jarvis-waveform: {self.WAVEFORM};
            --jarvis-border: {self.BORDER};
            --jarvis-border-active: {self.BORDER_ACTIVE};
        """

    def to_rgb_tuple(self, hex_color: str) -> tuple:
        """Convierte un color hex a tupla (r, g, b) para Cairo."""
        h = hex_color.lstrip('#')
        if len(h) == 6:
            return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        return (1.0, 1.0, 1.0)

    def to_rgba_tuple(self, hex_color: str, alpha: float = 1.0) -> tuple:
        """Convierte un color hex a tupla (r, g, b, a) para Cairo."""
        rgb = self.to_rgb_tuple(hex_color)
        return (*rgb, alpha)


# ─────────────────────────────────────────────────────────────────────────────
# PALETAS PREDEFINIDAS
# ─────────────────────────────────────────────────────────────────────────────

PALETA_CLASSIC = Paleta(
    nombre="jarvis_classic",
    descripcion="Cyan eléctrico sobre negro profundo — el Jarvis original",
    PRIMARY="#00CFFF",
    SECONDARY="#0088FF",
    ACCENT="#00FFEE",
    BACKGROUND="#05080F",
    SURFACE="#0A0F1E",
    SURFACE_2="#111827",
    TEXT="#E8F4FF",
    TEXT_DIM="#6B8AAA",
    TEXT_ACCENT="#05080F",
    SUCCESS="#00FF9D",
    WARNING="#FFB800",
    ERROR="#FF3D71",
    GLOW="#00CFFF",
    GLOW_2="#0044AA",
    PARTICLE="#00CFFF",
    PARTICLE_DIM="#003366",
    WAVEFORM="#00FFEE",
    BORDER="#1A2A3A",
    BORDER_ACTIVE="#00CFFF",
)

PALETA_CYBER = Paleta(
    nombre="jarvis_cyber",
    descripcion="Verde neón cyberpunk sobre negro — Matrix vibes",
    PRIMARY="#00FF7F",
    SECONDARY="#00CC55",
    ACCENT="#AAFF00",
    BACKGROUND="#030A03",
    SURFACE="#071507",
    SURFACE_2="#0D200D",
    TEXT="#CCFFCC",
    TEXT_DIM="#4A8A4A",
    TEXT_ACCENT="#030A03",
    SUCCESS="#00FF7F",
    WARNING="#FFD700",
    ERROR="#FF4444",
    GLOW="#00FF7F",
    GLOW_2="#004422",
    PARTICLE="#00FF7F",
    PARTICLE_DIM="#004420",
    WAVEFORM="#AAFF00",
    BORDER="#0A2A0A",
    BORDER_ACTIVE="#00FF7F",
)

PALETA_RED = Paleta(
    nombre="jarvis_red",
    descripcion="Rojo y naranja energéticos — intensidad máxima",
    PRIMARY="#FF3D71",
    SECONDARY="#FF8F00",
    ACCENT="#FF6B00",
    BACKGROUND="#0F0305",
    SURFACE="#1A0608",
    SURFACE_2="#250A0D",
    TEXT="#FFE8EC",
    TEXT_DIM="#9A4455",
    TEXT_ACCENT="#0F0305",
    SUCCESS="#00FF9D",
    WARNING="#FF8F00",
    ERROR="#FF3D71",
    GLOW="#FF3D71",
    GLOW_2="#660020",
    PARTICLE="#FF3D71",
    PARTICLE_DIM="#550020",
    WAVEFORM="#FF8F00",
    BORDER="#2A0A10",
    BORDER_ACTIVE="#FF3D71",
)

PALETA_AMBER = Paleta(
    nombre="jarvis_amber",
    descripcion="Ámbar dorado premium — cálido y elegante",
    PRIMARY="#FFB800",
    SECONDARY="#FF8C00",
    ACCENT="#FFDD44",
    BACKGROUND="#080600",
    SURFACE="#140E00",
    SURFACE_2="#1E1500",
    TEXT="#FFF8E0",
    TEXT_DIM="#8A6A00",
    TEXT_ACCENT="#080600",
    SUCCESS="#00D97E",
    WARNING="#FFB800",
    ERROR="#FF4444",
    GLOW="#FFB800",
    GLOW_2="#554400",
    PARTICLE="#FFB800",
    PARTICLE_DIM="#443300",
    WAVEFORM="#FFDD44",
    BORDER="#2A1E00",
    BORDER_ACTIVE="#FFB800",
)

PALETA_NEUTRAL = Paleta(
    nombre="jarvis_neutral",
    descripcion="Blanco y gris — minimalismo profesional",
    PRIMARY="#64B5F6",
    SECONDARY="#90CAF9",
    ACCENT="#42A5F5",
    BACKGROUND="#0F1015",
    SURFACE="#1A1D24",
    SURFACE_2="#232730",
    TEXT="#E8EDF5",
    TEXT_DIM="#6B7585",
    TEXT_ACCENT="#0F1015",
    SUCCESS="#4CAF50",
    WARNING="#FFC107",
    ERROR="#F44336",
    GLOW="#64B5F6",
    GLOW_2="#1A3A5A",
    PARTICLE="#64B5F6",
    PARTICLE_DIM="#1A3050",
    WAVEFORM="#90CAF9",
    BORDER="#2A2F3A",
    BORDER_ACTIVE="#64B5F6",
)

PALETA_HIGH_CONTRAST = Paleta(
    nombre="jarvis_high_contrast",
    descripcion="Alto contraste negro/amarillo/blanco — máxima legibilidad",
    PRIMARY="#FFFF00",
    SECONDARY="#00FFFF",
    ACCENT="#FFFFFF",
    BACKGROUND="#000000",
    SURFACE="#121212",
    SURFACE_2="#242424",
    TEXT="#FFFFFF",
    TEXT_DIM="#CCCCCC",
    TEXT_ACCENT="#000000",
    SUCCESS="#00FF00",
    WARNING="#FFFF00",
    ERROR="#FF0000",
    GLOW="#FFFF00",
    GLOW_2="#888800",
    PARTICLE="#FFFF00",
    PARTICLE_DIM="#666600",
    WAVEFORM="#00FFFF",
    BORDER="#FFFFFF",
    BORDER_ACTIVE="#FFFF00",
)


# ─────────────────────────────────────────────────────────────────────────────
# GESTOR DE TEMAS
# ─────────────────────────────────────────────────────────────────────────────

class GestorTemas:
    """
    Gestor centralizado de paletas de color.

    Mantiene el registro de paletas disponibles y la paleta activa.
    Permite cambio de tema en tiempo de ejecución.
    """

    PALETAS_DISPONIBLES: Dict[str, Paleta] = {
        "jarvis_classic": PALETA_CLASSIC,
        "jarvis_cyber": PALETA_CYBER,
        "jarvis_red": PALETA_RED,
        "jarvis_amber": PALETA_AMBER,
        "jarvis_neutral": PALETA_NEUTRAL,
        "jarvis_high_contrast": PALETA_HIGH_CONTRAST,
    }

    PALETA_DEFAULT = "jarvis_classic"

    def __init__(self) -> None:
        self._paleta_activa: Paleta = PALETA_CLASSIC
        self._nombre_activo: str = self.PALETA_DEFAULT

    def obtener_paleta(self) -> Paleta:
        """Devuelve la paleta activa."""
        return self._paleta_activa

    def obtener_nombre(self) -> str:
        """Devuelve el nombre de la paleta activa."""
        return self._nombre_activo

    def cambiar_tema(self, nombre: str) -> bool:
        """
        Cambia la paleta activa.

        Args:
            nombre: Nombre de la paleta (e.g. 'jarvis_cyber').

        Returns:
            True si se cambió correctamente, False si no existe.
        """
        if nombre not in self.PALETAS_DISPONIBLES:
            logger.warning("Paleta '%s' no encontrada. Disponibles: %s",
                          nombre, list(self.PALETAS_DISPONIBLES.keys()))
            return False

        self._paleta_activa = self.PALETAS_DISPONIBLES[nombre]
        self._nombre_activo = nombre
        logger.info("Tema cambiado a: %s", nombre)

        # Emitir evento de cambio de tema
        from eventos.bus import bus, Eventos
        bus.emitir(Eventos.CAMBIO_TEMA, {"nombre_tema": nombre})

        # Persistir preferencia
        try:
            from nucleo.memoria import guardar_preferencia
            guardar_preferencia("ui_tema", nombre)
        except Exception as e:
            logger.debug("No se pudo persistir tema: %s", e)

        return True

    def cargar_tema_guardado(self) -> None:
        """Carga el tema guardado en preferencias de la memoria."""
        try:
            from nucleo.memoria import obtener_preferencia
            tema_guardado = obtener_preferencia("ui_tema", self.PALETA_DEFAULT)
            self.cambiar_tema(tema_guardado)
        except Exception as e:
            logger.debug("No se pudo cargar tema guardado: %s", e)

    def listar_temas(self) -> list:
        """Devuelve la lista de temas disponibles."""
        return list(self.PALETAS_DISPONIBLES.keys())

    def registrar_paleta_custom(self, paleta: Paleta) -> None:
        """
        Registra una paleta personalizada.

        Args:
            paleta: Objeto Paleta con los colores definidos.
        """
        self.PALETAS_DISPONIBLES[paleta.nombre] = paleta
        logger.info("Paleta personalizada registrada: %s", paleta.nombre)


# Instancia singleton global
gestor_temas = GestorTemas()
