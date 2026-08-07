#!/usr/bin/env python3
"""Script de verificación del venv."""
import sys
print(f"Python: {sys.version}")
print(f"Executable: {sys.executable}")

try:
    import gi
    print(f"gi OK: {gi.__file__}")
except ImportError as e:
    print(f"ERROR gi: {e}")
    sys.exit(1)

try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    print(f"GTK4 OK: {Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}")
except Exception as e:
    print(f"ERROR GTK4: {e}")
    sys.exit(1)

print("Todo OK")
