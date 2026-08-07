"""
plugins/calculadora.py — Plugin de calculadora científica de Jarvis.

Soporta:
- Operaciones básicas: suma, resta, multiplicación, división
- Potencias: "2 elevado a 8", "2 al cuadrado"
- Raíces: "raíz de 16", "raíz cuadrada de 25"
- Porcentajes: "15 porciento de 200"
- Logaritmos: "logaritmo de 100"
- Trigonometría: "seno de 45", "coseno de 90"
- Conversiones básicas: temperatura, longitud
"""

import logging
import math
import re
from typing import Optional

import plugins

logger = logging.getLogger("jarvis.calculadora")

# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZACIONES DE LENGUAJE NATURAL → EXPRESIÓN MATEMÁTICA
# ─────────────────────────────────────────────────────────────────────────────

PALABRAS_OPERADORES: dict[str, str] = {
    "más": "+", "mas": "+", "sumado a": "+", "más que": "+",
    "menos": "-", "restado": "-", "menos que": "-",
    "por": "*", "multiplicado por": "*", "veces": "*",
    "entre": "/", "dividido entre": "/", "dividido por": "/", "sobre": "/",
}

PALABRAS_NUMEROS: dict[str, str] = {
    "cero": "0", "un": "1", "uno": "1", "dos": "2",
    "tres": "3", "cuatro": "4", "cinco": "5", "seis": "6",
    "siete": "7", "ocho": "8", "nueve": "9", "diez": "10",
    "once": "11", "doce": "12", "trece": "13", "catorce": "14",
    "quince": "15", "veinte": "20", "treinta": "30", "cuarenta": "40",
    "cincuenta": "50", "cien": "100", "mil": "1000",
}

# Entorno seguro para eval(): solo funciones matemáticas
_ENTORNO_SEGURO = {
    "__builtins__": {},
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "pi": math.pi,
    "e": math.e,
    "pow": math.pow,
    "floor": math.floor,
    "ceil": math.ceil,
    "factorial": math.factorial,
}


def _normalizar_expresion(texto: str) -> Optional[str]:
    """
    Convierte lenguaje natural a una expresión matemática evaluable.

    Args:
        texto: Expresión en lenguaje natural (ya normalizada).

    Returns:
        String de expresión Python o None si no se pudo convertir.
    """
    expr = texto.strip().lower()

    # ── Raíz cuadrada ─────────────────────────────────────────────────────────
    m = re.search(r"ra[íi]z\s+(?:cuadrada\s+)?de\s+([\d.]+)", expr)
    if m:
        return f"sqrt({m.group(1)})"

    # ── Potencia ──────────────────────────────────────────────────────────────
    m = re.search(r"([\d.]+)\s+(?:elevado\s+a|elevado\s+al?|al\s+cubo|al\s+cuadrado|a\s+la\s+\w+\s+potencia)\s*([\d.]*)", expr)
    if m:
        base = m.group(1)
        if "cubo" in expr:
            return f"{base}**3"
        if "cuadrado" in expr:
            return f"{base}**2"
        exp = m.group(2)
        if exp:
            return f"{base}**{exp}"

    m = re.search(r"([\d.]+)\s+a\s+la\s+([\d.]+)", expr)
    if m:
        return f"{m.group(1)}**{m.group(2)}"

    # ── Porcentaje ────────────────────────────────────────────────────────────
    m = re.search(r"([\d.]+)\s+(?:por\s*ciento|porciento|%)\s+de\s+([\d.]+)", expr)
    if m:
        return f"({m.group(1)} / 100) * {m.group(2)}"

    # ── Logaritmo ─────────────────────────────────────────────────────────────
    m = re.search(r"logaritmo\s+(?:natural\s+)?de\s+([\d.]+)", expr)
    if m:
        return f"log({m.group(1)})"

    m = re.search(r"log(?:aritmo)?\s+(?:base\s+10\s+)?de\s+([\d.]+)", expr)
    if m:
        return f"log10({m.group(1)})"

    # ── Trigonometría (grados → radianes) ─────────────────────────────────────
    for func in ("seno", "coseno", "tangente", "sin", "cos", "tan"):
        m = re.search(rf"{func}\s+de\s+([\d.]+)", expr)
        if m:
            grados = float(m.group(1))
            rad = math.radians(grados)
            func_map = {
                "seno": "sin", "sin": "sin",
                "coseno": "cos", "cos": "cos",
                "tangente": "tan", "tan": "tan",
            }
            return f"{func_map[func]}({rad})"

    # ── Factorial ─────────────────────────────────────────────────────────────
    m = re.search(r"factorial\s+de\s+([\d]+)", expr)
    if m:
        return f"factorial({m.group(1)})"

    # ── Reemplazar palabras de operadores ─────────────────────────────────────
    for palabra, simbolo in sorted(PALABRAS_OPERADORES.items(), key=lambda x: -len(x[0])):
        expr = expr.replace(palabra, simbolo)

    # ── Reemplazar palabras de números ────────────────────────────────────────
    for palabra, numero in sorted(PALABRAS_NUMEROS.items(), key=lambda x: -len(x[0])):
        expr = re.sub(rf"\b{palabra}\b", numero, expr)

    # ── Limpiar tokens no matemáticos ─────────────────────────────────────────
    expr = re.sub(r"[^\d\s\+\-\*\/\.\(\)\^]", " ", expr)
    expr = expr.replace("^", "**")
    expr = re.sub(r"\s+", " ", expr).strip()
    expr = re.sub(r"\s+", " ", expr).strip()
    expr = re.sub(r"(\d)\s+(\d)", r"\1 + \2", expr)  # "5 3" → "5 + 3" (fallback)

    # Validar que quede algo evaluable
    if re.search(r"\d", expr):
        return expr

    return None


def _formatear_resultado(valor: float) -> str:
    """Formatea el resultado evitando decimales innecesarios."""
    if valor == int(valor) and abs(valor) < 1e15:
        return str(int(valor))
    return f"{valor:.6g}"


def evaluar(expresion: str) -> Optional[float]:
    """
    Evalúa una expresión matemática de forma segura.

    Args:
        expresion: String de expresión Python (sin variables peligrosas).

    Returns:
        Resultado numérico o None si hay error.
    """
    try:
        resultado = eval(expresion, _ENTORNO_SEGURO)  # noqa: S307
        if isinstance(resultado, (int, float)) and not math.isnan(resultado):
            return float(resultado)
        return None
    except (ZeroDivisionError, ValueError, TypeError, SyntaxError, OverflowError) as e:
        logger.warning("Error evaluando '%s': %s", expresion, e)
        return None
    except Exception as e:
        logger.error("Error inesperado en eval: %s", e)
        return None


class PluginCalculadora(plugins.BasePlugin):
    """Plugin de calculadora científica con soporte de lenguaje natural."""

    def __init__(self) -> None:
        super().__init__(
            nombre="calculadora",
            intenciones=["CALCULAR"],
            descripcion=(
                "Calcula operaciones matemáticas. "
                "Ej: 'cuánto es raíz de 144', '15 porciento de 200'."
            ),
            categoria="Utilidades",
        )

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        expresion_raw = entidades.get("expresion", "").strip()

        if not expresion_raw:
            return "¿Qué deseas calcular?"

        expresion_norm = _normalizar_expresion(expresion_raw)

        if not expresion_norm:
            return f"No pude interpretar la expresión '{expresion_raw}'. ¿Puedes formularla de otra manera?"

        resultado = evaluar(expresion_norm)

        if resultado is None:
            return "No pude calcular eso. Revisa la expresión."

        resultado_str = _formatear_resultado(resultado)
        return f"El resultado es {resultado_str}."


plugins.registrar(PluginCalculadora())
