# modulos/contexto.py
import subprocess
from nucleo.voz import hablar

def cambiar_ventana(nombre_app):
    nombre_app = nombre_app.lower()
    try:
        hablar(f"Cambiando el foco a {nombre_app}.")
        # wmctrl busca ventanas abiertas que coincidan parcialmente con el nombre
        subprocess.run(["wmctrl", "-a", nombre_app], check=True)
    except subprocess.CalledProcessError:
        hablar(f"No encontré ninguna ventana abierta llamada {nombre_app}.")
    except Exception as e:
        hablar(f"Error al intentar cambiar de ventana: {e}")