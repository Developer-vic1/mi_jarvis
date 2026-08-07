# modulos/sistema.py
import subprocess
import os
from nucleo.voz import hablar

def abrir_programa(nombre):
    from modulos.gestor_aplicaciones import gestor_apps_sistema
    nombre_lower = nombre.lower()
    try:
        ok, msg = gestor_apps_sistema.abrir_aplicacion(nombre_lower)
        hablar(msg)
    except Exception as e:
        hablar(f"Ocurrió un error al intentar abrir el programa: {e}")

def abrir_carpeta(nombre_carpeta):
    home = os.path.expanduser("~")
    ruta = home
    
    nombre_carpeta = nombre_carpeta.lower()
    if "descargas" in nombre_carpeta:
        ruta = os.path.join(home, "Downloads")
    elif "documentos" in nombre_carpeta:
        ruta = os.path.join(home, "Documents")
    elif "escritorio" in nombre_carpeta:
        ruta = os.path.join(home, "Desktop")
    elif "proyecto" in nombre_carpeta or "jarvis" in nombre_carpeta:
        ruta = os.path.join(home, "mi_jarvis")

    try:
        hablar("Abriendo carpeta.")
        subprocess.Popen(["xdg-open", ruta])
    except Exception as e:
        hablar(f"No pude abrir la carpeta solicitada: {e}")