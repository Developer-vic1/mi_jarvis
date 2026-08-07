"""
interfaz/nucleo_visual.py — Núcleo visual animado de Jarvis.

Implementa el elemento central de la interfaz: una esfera energética animada
con partículas, ondas y pulsaciones que reacciona al estado real del asistente.

Tecnología: GTK4 DrawingArea + Cairo 2D rendering + GLib.timeout_add

Estados visuales:
    REPOSO       → Pulso lento, partículas mínimas, brillo bajo
    DESPERTANDO  → Expansión desde el centro, energía creciente
    ESCUCHANDO   → Ondas concéntricas, partículas reactivas
    PROCESANDO   → Rotación de partículas, actividad neural
    EJECUTANDO   → Espiral de partículas, núcleo expansivo
    HABLANDO     → Waveform animado, ondas rítmicas
    EXITO        → Expansión suave y contracción, brillo verde
    ERROR        → Vibración rápida, color rojo
    ESPERANDO    → Pulso intermitente ámbar
"""

import math
import random
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import gi
gi.require_version("Gtk", "4.0")
try:
    gi.require_foreign("cairo")
except Exception:
    pass
import cairo
from gi.repository import Gtk, GLib, Gdk

logger = logging.getLogger("jarvis.interfaz.nucleo_visual")


@dataclass
class Particula:
    """Partícula individual del campo de energía del núcleo."""
    x: float          # Posición X (0.0 a 1.0 relativo al canvas)
    y: float          # Posición Y
    vx: float         # Velocidad X
    vy: float         # Velocidad Y
    radio: float      # Radio de la partícula
    alpha: float      # Transparencia (0.0 a 1.0)
    vida: float       # Vida restante (0.0 a 1.0)
    vida_max: float   # Vida máxima en segundos
    creada: float     # Timestamp de creación
    angulo: float     # Ángulo orbital
    distancia: float  # Distancia al centro
    velocidad_ang: float  # Velocidad angular


@dataclass
class OndaExpansion:
    """Onda de expansión circular emanando del núcleo."""
    radio: float      # Radio actual
    radio_max: float  # Radio máximo antes de desaparecer
    alpha: float      # Transparencia actual
    grosor: float     # Grosor del borde
    creada: float     # Timestamp de creación


class NucleoVisual(Gtk.DrawingArea):
    """
    Widget de dibujo del núcleo energético de Jarvis.

    Hereda de Gtk.DrawingArea y usa Cairo para renderizar:
    - Esfera central con gradiente radial y resplandor
    - Partículas orbitales y libres
    - Ondas de expansión
    - Anillos de energía
    - Waveform de audio simulado/real

    Se integra con el EventBus para reaccionar a estados reales.
    """

    # Frecuencia de actualización (ms)
    FPS_REPOSO = 60      # 1 fps en reposo para ahorrar CPU
    FPS_ACTIVO = 1000 // 60  # ~60 fps cuando activo

    # Estados internos del núcleo
    ESTADO_REPOSO = "reposo"
    ESTADO_DESPERTANDO = "despertando"
    ESTADO_ESCUCHANDO = "escuchando"
    ESTADO_PROCESANDO = "procesando"
    ESTADO_EJECUTANDO = "ejecutando"
    ESTADO_HABLANDO = "hablando"
    ESTADO_EXITO = "exito"
    ESTADO_ERROR = "error"
    ESTADO_ESPERANDO = "esperando"

    def __init__(self) -> None:
        super().__init__()

        # Estado actual
        self._estado = self.ESTADO_REPOSO
        self._estado_anterior = self.ESTADO_REPOSO

        # Tiempo y animación
        self._tiempo_inicio = time.time()
        self._tiempo_estado = time.time()  # Cuándo entró en este estado
        self._frame = 0

        # Partículas
        self._particulas: List[Particula] = []
        self._max_particulas = 80
        self._ondas: List[OndaExpansion] = []
        self._ultima_onda = 0.0

        # Audio reactivo
        self._nivel_audio = 0.0      # 0.0 a 1.0
        self._amplitudes = [0.0] * 32  # Buffer de amplitudes para waveform

        # Parámetros de animación por estado
        self._intensidad = 0.3       # 0.0 a 1.0
        self._velocidad = 0.3        # Factor velocidad de partículas
        self._pulso_fase = 0.0       # Fase del pulso principal
        self._rotacion = 0.0         # Ángulo de rotación global
        self._vibra_x = 0.0          # Vibración para estado ERROR
        self._vibra_y = 0.0
        self._expansion = 1.0        # Factor de expansión del núcleo

        # Paleta de color
        self._paleta = None
        self._cargar_paleta()

        # Timer principal de animación
        self._timer_id: Optional[int] = None
        self._iniciar_timer()

        # Configurar DrawingArea
        self.set_draw_func(self._dibujar)
        self.set_content_width(280)
        self.set_content_height(280)

        # Inicializar partículas
        self._inicializar_particulas()

        logger.info("NucleoVisual inicializado.")

    def _cargar_paleta(self) -> None:
        """Carga la paleta activa del gestor de temas."""
        try:
            from temas.gestor_temas import gestor_temas
            self._paleta = gestor_temas.obtener_paleta()
        except Exception as e:
            logger.debug("Paleta no disponible, usando defaults: %s", e)
            self._paleta = None

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Convierte hex a tupla RGB 0.0-1.0."""
        h = hex_color.lstrip('#')
        if len(h) != 6:
            return (0.0, 1.0, 1.0)
        return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

    def _get_color_estado(self) -> tuple:
        """Devuelve el color RGB del estado actual."""
        if self._paleta is None:
            colores_default = {
                self.ESTADO_REPOSO:      "#004488",
                self.ESTADO_DESPERTANDO: "#00CFFF",
                self.ESTADO_ESCUCHANDO:  "#00CFFF",
                self.ESTADO_PROCESANDO:  "#0088FF",
                self.ESTADO_EJECUTANDO:  "#00FFEE",
                self.ESTADO_HABLANDO:    "#00CFFF",
                self.ESTADO_EXITO:       "#00FF9D",
                self.ESTADO_ERROR:       "#FF3D71",
                self.ESTADO_ESPERANDO:   "#FFB800",
            }
            return self._hex_to_rgb(colores_default.get(self._estado, "#00CFFF"))

        color_map = {
            self.ESTADO_REPOSO:      self._paleta.GLOW,
            self.ESTADO_DESPERTANDO: self._paleta.PRIMARY,
            self.ESTADO_ESCUCHANDO:  self._paleta.PRIMARY,
            self.ESTADO_PROCESANDO:  self._paleta.SECONDARY,
            self.ESTADO_EJECUTANDO:  self._paleta.ACCENT,
            self.ESTADO_HABLANDO:    self._paleta.PRIMARY,
            self.ESTADO_EXITO:       self._paleta.SUCCESS,
            self.ESTADO_ERROR:       self._paleta.ERROR,
            self.ESTADO_ESPERANDO:   self._paleta.WARNING,
        }
        return self._hex_to_rgb(color_map.get(self._estado, self._paleta.PRIMARY))

    def _inicializar_particulas(self) -> None:
        """Crea el conjunto inicial de partículas orbitales."""
        self._particulas.clear()
        n = 30
        for i in range(n):
            angulo = (2 * math.pi * i / n) + random.uniform(-0.3, 0.3)
            distancia = random.uniform(0.25, 0.42)
            self._particulas.append(Particula(
                x=0.5 + math.cos(angulo) * distancia,
                y=0.5 + math.sin(angulo) * distancia,
                vx=0.0, vy=0.0,
                radio=random.uniform(1.5, 3.5),
                alpha=random.uniform(0.4, 0.9),
                vida=1.0,
                vida_max=random.uniform(3.0, 8.0),
                creada=time.time() - random.uniform(0, 5.0),
                angulo=angulo,
                distancia=distancia,
                velocidad_ang=random.uniform(0.3, 0.8) * (1 if random.random() > 0.3 else -1),
            ))

    def _iniciar_timer(self) -> None:
        """Inicia el timer de animación."""
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        fps = self.FPS_REPOSO if self._estado == self.ESTADO_REPOSO else self.FPS_ACTIVO
        self._timer_id = GLib.timeout_add(fps, self._on_tick)

    def _on_tick(self) -> bool:
        """Callback del timer: actualiza física y solicita redibujado."""
        t = time.time()
        dt = 1.0 / 60.0

        self._frame += 1
        self._pulso_fase += dt * (1.5 + self._intensidad * 3.0)
        self._rotacion += dt * self._velocidad * 0.5

        # Actualizar estado de animación
        self._actualizar_estado_animacion(t, dt)

        # Actualizar partículas
        self._actualizar_particulas(t, dt)

        # Actualizar ondas
        self._actualizar_ondas(t, dt)

        # Solicitar redibujado
        self.queue_draw()

        return True  # Continuar el timer

    def _actualizar_estado_animacion(self, t: float, dt: float) -> None:
        """Actualiza los parámetros de animación según el estado actual."""
        tiempo_en_estado = t - self._tiempo_estado

        if self._estado == self.ESTADO_REPOSO:
            target_intensidad = 0.2
            target_velocidad = 0.15
            self._expansion = 0.85 + 0.05 * math.sin(self._pulso_fase * 0.4)

        elif self._estado == self.ESTADO_DESPERTANDO:
            target_intensidad = 0.9
            target_velocidad = 1.5
            factor = min(tiempo_en_estado / 0.8, 1.0)
            self._expansion = 0.85 + factor * 0.3

        elif self._estado == self.ESTADO_ESCUCHANDO:
            target_intensidad = 0.7 + 0.3 * max(0, self._nivel_audio)
            target_velocidad = 0.8 + self._nivel_audio * 0.5
            self._expansion = 1.0 + 0.1 * math.sin(self._pulso_fase * 2.0) + self._nivel_audio * 0.15

        elif self._estado == self.ESTADO_PROCESANDO:
            target_intensidad = 0.75
            target_velocidad = 1.2
            self._expansion = 1.0 + 0.08 * math.sin(self._pulso_fase * 4.0)

        elif self._estado == self.ESTADO_EJECUTANDO:
            target_intensidad = 0.85
            target_velocidad = 1.8
            self._expansion = 1.0 + 0.12 * abs(math.sin(self._pulso_fase * 5.0))

        elif self._estado == self.ESTADO_HABLANDO:
            target_intensidad = 0.8 + 0.2 * max(0, self._nivel_audio)
            target_velocidad = 1.0
            self._expansion = 1.0 + 0.15 * abs(math.sin(self._pulso_fase * 6.0))

        elif self._estado == self.ESTADO_EXITO:
            target_intensidad = 0.9
            target_velocidad = 0.6
            factor = min(tiempo_en_estado / 0.5, 1.0)
            self._expansion = 1.0 + 0.2 * math.sin(factor * math.pi) * (1 - tiempo_en_estado * 0.3)
            self._expansion = max(0.85, self._expansion)

        elif self._estado == self.ESTADO_ERROR:
            target_intensidad = 0.95
            target_velocidad = 0.5
            frecuencia_vibra = 15.0
            amp = max(0, 1.0 - tiempo_en_estado * 2.0) * 5
            self._vibra_x = math.sin(t * frecuencia_vibra * 2 * math.pi) * amp
            self._vibra_y = math.cos(t * frecuencia_vibra * 1.7 * 2 * math.pi) * amp * 0.5
            self._expansion = 0.95

        elif self._estado == self.ESTADO_ESPERANDO:
            target_intensidad = 0.5 + 0.3 * abs(math.sin(self._pulso_fase * 1.5))
            target_velocidad = 0.4
            self._expansion = 0.95 + 0.08 * abs(math.sin(self._pulso_fase * 1.5))

        else:
            target_intensidad = 0.5
            target_velocidad = 0.5

        # Interpolación suave (lerp)
        lerp = 0.08
        self._intensidad += (target_intensidad - self._intensidad) * lerp
        self._velocidad += (target_velocidad - self._velocidad) * lerp

    def _actualizar_particulas(self, t: float, dt: float) -> None:
        """Actualiza posición y ciclo de vida de cada partícula."""
        multiplicador_vel = self._velocidad

        # Agregar nuevas partículas según el estado
        n_agregar = 0
        if self._estado in (self.ESTADO_EJECUTANDO, self.ESTADO_DESPERTANDO):
            n_agregar = 2
        elif self._estado in (self.ESTADO_PROCESANDO, self.ESTADO_HABLANDO, self.ESTADO_ESCUCHANDO):
            n_agregar = 1
        elif self._estado == self.ESTADO_REPOSO:
            n_agregar = 0 if len(self._particulas) > 20 else 1

        for _ in range(n_agregar):
            if len(self._particulas) < self._max_particulas:
                angulo = random.uniform(0, 2 * math.pi)
                dist = random.uniform(0.15, 0.45)
                self._particulas.append(Particula(
                    x=0.5 + math.cos(angulo) * dist,
                    y=0.5 + math.sin(angulo) * dist,
                    vx=random.uniform(-0.02, 0.02) * multiplicador_vel,
                    vy=random.uniform(-0.02, 0.02) * multiplicador_vel,
                    radio=random.uniform(1.0, 4.0),
                    alpha=random.uniform(0.5, 1.0),
                    vida=1.0,
                    vida_max=random.uniform(2.0, 6.0),
                    creada=t,
                    angulo=angulo,
                    distancia=dist,
                    velocidad_ang=random.uniform(0.3, 1.2) * multiplicador_vel * (1 if random.random() > 0.3 else -1),
                ))

        # Actualizar partículas existentes
        particulas_vivas = []
        for p in self._particulas:
            edad = t - p.creada
            p.vida = max(0.0, 1.0 - edad / p.vida_max)

            if p.vida <= 0:
                continue

            # Movimiento orbital
            p.angulo += p.velocidad_ang * dt * multiplicador_vel
            p.distancia += random.uniform(-0.001, 0.001)
            p.distancia = max(0.10, min(0.48, p.distancia))

            p.x = 0.5 + math.cos(p.angulo) * p.distancia
            p.y = 0.5 + math.sin(p.angulo) * p.distancia

            particulas_vivas.append(p)

        self._particulas = particulas_vivas

    def _actualizar_ondas(self, t: float, dt: float) -> None:
        """Actualiza el ciclo de vida de las ondas de expansión."""
        # Generar nuevas ondas según el estado
        intervalo_onda = {
            self.ESTADO_REPOSO: 4.0,
            self.ESTADO_DESPERTANDO: 0.3,
            self.ESTADO_ESCUCHANDO: 0.8,
            self.ESTADO_PROCESANDO: 0.5,
            self.ESTADO_EJECUTANDO: 0.4,
            self.ESTADO_HABLANDO: 0.3,
            self.ESTADO_EXITO: 0.2,
            self.ESTADO_ERROR: 0.15,
            self.ESTADO_ESPERANDO: 1.5,
        }.get(self._estado, 1.0)

        if t - self._ultima_onda > intervalo_onda:
            self._ondas.append(OndaExpansion(
                radio=0.15,
                radio_max=0.52,
                alpha=0.7,
                grosor=1.5,
                creada=t,
            ))
            self._ultima_onda = t

        # Actualizar ondas existentes
        ondas_vivas = []
        for onda in self._ondas:
            progreso = (onda.radio - 0.15) / (onda.radio_max - 0.15)
            onda.radio += dt * 0.25
            onda.alpha = 0.7 * (1.0 - progreso)
            onda.grosor = 2.0 * (1.0 - progreso * 0.7)

            if onda.radio < onda.radio_max and onda.alpha > 0.02:
                ondas_vivas.append(onda)

        self._ondas = ondas_vivas

    # ─── RENDERIZADO CAIRO ───────────────────────────────────────────────────

    def _dibujar(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        """Función principal de renderizado. Llamada por GTK en cada frame."""
        try:
            cx, cy = width / 2, height / 2
            r = min(width, height) / 2 - 10

            # Colores del estado actual
            color = self._get_color_estado()
            cr_r, cr_g, cr_b = color

            # Limpiar con fondo transparente
            cr.save()
            cr.set_operator(1)  # OPERATOR_OVER
            cr.set_source_rgba(0, 0, 0, 0)
            cr.paint()
            cr.restore()

            # Aplicar vibración si hay error
            if self._estado == self.ESTADO_ERROR:
                cr.translate(self._vibra_x, self._vibra_y)

            # ── 1. Resplandor exterior difuso ────────────────────────────────────
            self._dibujar_resplandor(cr, cx, cy, r, cr_r, cr_g, cr_b)

            # ── 2. Ondas de expansión ────────────────────────────────────────────
            self._dibujar_ondas(cr, cx, cy, r, cr_r, cr_g, cr_b)

            # ── 3. Anillos de energía ────────────────────────────────────────────
            self._dibujar_anillos(cr, cx, cy, r, cr_r, cr_g, cr_b)

            # ── 4. Conexiones tipo red neuronal (PROCESANDO / EJECUTANDO) ───────
            if self._estado in (self.ESTADO_PROCESANDO, self.ESTADO_EJECUTANDO, self.ESTADO_DESPERTANDO):
                self._dibujar_red_neural(cr, cx, cy, r, cr_r, cr_g, cr_b)

            # ── 5. Partículas orbitales ──────────────────────────────────────────
            self._dibujar_particulas(cr, cx, cy, r, cr_r, cr_g, cr_b)

            # ── 6. Núcleo central (esfera) ───────────────────────────────────────
            self._dibujar_nucleo(cr, cx, cy, r, cr_r, cr_g, cr_b)

            # ── 7. Waveform de audio (en estado HABLANDO/ESCUCHANDO) ─────────────
            if self._estado in (self.ESTADO_HABLANDO, self.ESTADO_ESCUCHANDO):
                self._dibujar_waveform(cr, cx, cy, r, cr_r, cr_g, cr_b)

            # ── 8. Indicador de estado (punto central) ───────────────────────────
            self._dibujar_punto_central(cr, cx, cy, cr_r, cr_g, cr_b)

        except Exception as e:
            logger.error("Error en _dibujar NucleoVisual: %s", e)

    def _dibujar_red_neural(self, cr, cx, cy, r, cr_r, cr_g, cr_b):
        """Dibuja conexiones de energía tipo red neuronal entre partículas cercanas."""
        diam = min(cx * 2, cy * 2)
        coords = []
        for p in self._particulas:
            px = p.x * diam - (diam / 2 - cx)
            py = p.y * diam - (diam / 2 - cy)
            coords.append((px, py, p.alpha * p.vida))

        max_dist_sq = (r * 0.45) ** 2
        cr.set_line_width(0.8)
        for i in range(len(coords)):
            x1, y1, a1 = coords[i]
            for j in range(i + 1, min(i + 6, len(coords))):
                x2, y2, a2 = coords[j]
                dist_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
                if dist_sq < max_dist_sq:
                    factor = 1.0 - (dist_sq / max_dist_sq)
                    alpha_linea = factor * min(a1, a2) * self._intensidad * 0.6
                    if alpha_linea > 0.03:
                        cr.set_source_rgba(cr_r, cr_g, cr_b, alpha_linea)
                        cr.move_to(x1, y1)
                        cr.line_to(x2, y2)
                        cr.stroke()

    def _dibujar_resplandor(self, cr, cx, cy, r, cr_r, cr_g, cr_b):
        """Dibuja el halo de resplandor exterior."""
        radio_glow = r * self._expansion * (1.0 + self._intensidad * 0.4)
        import cairo
        pattern = cairo.RadialGradient(cx, cy, 0, cx, cy, radio_glow)
        alpha_glow = self._intensidad * 0.35
        pattern.add_color_stop_rgba(0.0, cr_r, cr_g, cr_b, alpha_glow)
        pattern.add_color_stop_rgba(0.4, cr_r, cr_g, cr_b, alpha_glow * 0.3)
        pattern.add_color_stop_rgba(1.0, cr_r, cr_g, cr_b, 0.0)
        cr.set_source(pattern)
        cr.arc(cx, cy, radio_glow, 0, 2 * math.pi)
        cr.fill()

    def _dibujar_ondas(self, cr, cx, cy, r, cr_r, cr_g, cr_b):
        """Dibuja las ondas de expansión circular."""
        for onda in self._ondas:
            radio_px = onda.radio * r * 2
            cr.set_source_rgba(cr_r, cr_g, cr_b, onda.alpha * self._intensidad)
            cr.set_line_width(onda.grosor)
            cr.arc(cx, cy, radio_px, 0, 2 * math.pi)
            cr.stroke()

    def _dibujar_anillos(self, cr, cx, cy, r, cr_r, cr_g, cr_b):
        """Dibuja anillos de energía concéntricos."""
        t = time.time()
        n_anillos = 2 if self._estado == self.ESTADO_REPOSO else 3

        for i in range(n_anillos):
            fase = (i / n_anillos) * 2 * math.pi
            radio_anillo = r * self._expansion * (0.6 + i * 0.12)
            alpha_anillo = 0.15 + 0.08 * math.sin(t * 2.0 + fase)
            alpha_anillo *= self._intensidad

            cr.set_source_rgba(cr_r, cr_g, cr_b, max(0, alpha_anillo))
            cr.set_line_width(0.8)
            cr.arc(cx, cy, radio_anillo, 0, 2 * math.pi)
            cr.stroke()

    def _dibujar_particulas(self, cr, cx, cy, r, cr_r, cr_g, cr_b):
        """Dibuja todas las partículas activas."""
        diam = min(cx * 2, cy * 2)
        for p in self._particulas:
            px = p.x * diam - (diam / 2 - cx)
            py = p.y * diam - (diam / 2 - cy)

            alpha_p = p.alpha * p.vida * self._intensidad
            if alpha_p < 0.02:
                continue

            # Núcleo brillante de la partícula
            cr.set_source_rgba(1.0, 1.0, 1.0, alpha_p * 0.8)
            cr.arc(px, py, p.radio * 0.4, 0, 2 * math.pi)
            cr.fill()

            # Halo de color de la partícula
            cr.set_source_rgba(cr_r, cr_g, cr_b, alpha_p * 0.5)
            cr.arc(px, py, p.radio, 0, 2 * math.pi)
            cr.fill()

    def _dibujar_nucleo(self, cr, cx, cy, r, cr_r, cr_g, cr_b):
        """Dibuja la esfera central con gradiente radial."""
        import cairo
        radio_nucleo = r * self._expansion * 0.35

        # Esfera con gradiente radial
        pattern = cairo.RadialGradient(
            cx - radio_nucleo * 0.25, cy - radio_nucleo * 0.25, 0,  # Luz interna
            cx, cy, radio_nucleo
        )

        # Centro brillante
        pattern.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.9)
        # Color primario
        pattern.add_color_stop_rgba(0.3, cr_r, cr_g, cr_b, 0.95)
        # Borde oscuro
        pattern.add_color_stop_rgba(0.7, cr_r * 0.3, cr_g * 0.3, cr_b * 0.3, 0.8)
        pattern.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.95)

        cr.set_source(pattern)
        cr.arc(cx, cy, radio_nucleo, 0, 2 * math.pi)
        cr.fill()

        # Borde luminoso del núcleo
        cr.set_source_rgba(cr_r, cr_g, cr_b, 0.6 * self._intensidad)
        cr.set_line_width(1.5)
        cr.arc(cx, cy, radio_nucleo, 0, 2 * math.pi)
        cr.stroke()

    def _dibujar_waveform(self, cr, cx, cy, r, cr_r, cr_g, cr_b):
        """Dibuja la forma de onda de audio alrededor del núcleo."""
        t = time.time()
        n_puntos = 64
        radio_base = r * self._expansion * 0.45

        cr.set_line_width(1.5)
        cr.set_source_rgba(cr_r, cr_g, cr_b, 0.7 * self._intensidad)

        for lado in (1, -1):  # Waveform arriba y abajo
            cr.new_path()
            for i in range(n_puntos + 1):
                angulo = (i / n_puntos) * 2 * math.pi

                # Generar amplitud sintética reactiva al audio
                amp = 0.0
                for j in range(3):
                    freq = (j + 1) * 3.5
                    fase_j = j * 1.2
                    amp += math.sin(t * freq + angulo * (j + 2) + fase_j) * (0.04 - j * 0.01)

                amp *= (1.0 + self._nivel_audio * 2.0) * self._intensidad
                radio_punto = radio_base + amp * r * lado

                x = cx + math.cos(angulo) * radio_punto
                y = cy + math.sin(angulo) * radio_punto

                if i == 0:
                    cr.move_to(x, y)
                else:
                    cr.line_to(x, y)

            cr.close_path()
            cr.stroke()

    def _dibujar_punto_central(self, cr, cx, cy, cr_r, cr_g, cr_b):
        """Dibuja el punto brillante central del núcleo."""
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.9)
        cr.arc(cx, cy, 2.5, 0, 2 * math.pi)
        cr.fill()

    # ─── API PÚBLICA ─────────────────────────────────────────────────────────

    def set_estado(self, estado: str) -> None:
        """
        Cambia el estado visual del núcleo.

        Args:
            estado: Una de las constantes ESTADO_* de esta clase.
        """
        if estado == self._estado:
            return

        self._estado_anterior = self._estado
        self._estado = estado
        self._tiempo_estado = time.time()

        # Reiniciar timer con FPS apropiado
        self._iniciar_timer()

        # Emitir onda inmediata en transiciones importantes
        if estado in (self.ESTADO_DESPERTANDO, self.ESTADO_EXITO, self.ESTADO_ERROR):
            self._ondas.append(OndaExpansion(
                radio=0.15, radio_max=0.52, alpha=0.9, grosor=2.5,
                creada=time.time()
            ))

        logger.debug("NucleoVisual: estado → %s", estado)

    def set_nivel_audio(self, nivel: float) -> None:
        """
        Actualiza el nivel de audio para la visualización reactiva.

        Args:
            nivel: Nivel de audio normalizado (0.0 a 1.0).
        """
        self._nivel_audio = max(0.0, min(1.0, nivel))

    def actualizar_paleta(self) -> None:
        """Recarga la paleta del gestor de temas."""
        self._cargar_paleta()

    def detener(self) -> None:
        """Detiene el timer de animación."""
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
