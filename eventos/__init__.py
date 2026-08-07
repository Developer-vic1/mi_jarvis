"""
eventos/__init__.py — Paquete de eventos de Jarvis.

Exporta el bus de eventos global para uso en todo el sistema.
"""

from eventos.bus import EventBus, bus

__all__ = ["EventBus", "bus"]
