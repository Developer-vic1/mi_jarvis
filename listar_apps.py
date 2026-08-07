# listar_apps.py
import os
import configparser

def listar_aplicaciones_sistema():
    directorios = [
        "/usr/share/applications/",
        os.path.expanduser("~/.local/share/applications/")
    ]
    
    print("\n" + "="*60)
    print("      REGISTRO DE APLICACIONES INSTALADAS EN LINUX")
    print("="*60 + "\n")
    
    total = 0
    vistas = set()

    for directorio in directorios:
        if not os.path.exists(directorio):
            continue
            
        for archivo in os.listdir(directorio):
            if archivo.endswith(".desktop"):
                ruta = os.path.join(directorio, archivo)
                try:
                    config = configparser.ConfigParser(interpolation=None)
                    config.read(ruta, encoding='utf-8')
                    
                    if config.has_section("Desktop Entry"):
                        # Omitir aplicaciones ocultas del sistema
                        if config.getboolean("Desktop Entry", "NoDisplay", fallback=False):
                            continue
                        if config.getboolean("Desktop Entry", "Hidden", fallback=False):
                            continue
                            
                        nombre = config.get("Desktop Entry", "Name", fallback="")
                        exec_cmd = config.get("Desktop Entry", "Exec", fallback="")
                        
                        if nombre and nombre not in vistas:
                            vistas.add(nombre)
                            print(f"Aplicación: {nombre}")
                            print(f"Comando (Exec): {exec_cmd}")
                            print("-" * 60)
                            total += 1
                except Exception:
                    pass
                    
    print(f"\nTotal de aplicaciones analizadas: {total}")

if __name__ == "__main__":
    listar_aplicaciones_sistema()