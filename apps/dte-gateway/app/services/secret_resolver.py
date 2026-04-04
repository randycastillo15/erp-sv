"""
Resuelve secretos del gateway desde variables de entorno del contenedor.
Ningún secreto viaja en requests HTTP — ni en la request de ERPNext al gateway,
ni en logs, ni en la respuesta.

Variables de entorno requeridas:
  MH_API_PASSWORD       — contraseña API del MH (para obtener token Bearer)
  FIRMADOR_PASSWORD_PRI — contraseña de la clave privada del firmador
"""

import os


def get_mh_api_password() -> str:
    """Retorna la contraseña del API MH desde env var MH_API_PASSWORD."""
    pwd = os.environ.get("MH_API_PASSWORD")
    if not pwd:
        raise RuntimeError(
            "Variable de entorno MH_API_PASSWORD no configurada. "
            "Agregar al archivo .env del gateway y montar en docker-compose."
        )
    return pwd


def get_firmador_password() -> str:
    """Retorna la contraseña de la clave privada desde env var FIRMADOR_PASSWORD_PRI."""
    pwd = os.environ.get("FIRMADOR_PASSWORD_PRI")
    if not pwd:
        raise RuntimeError(
            "Variable de entorno FIRMADOR_PASSWORD_PRI no configurada. "
            "Agregar al archivo .env del gateway y montar en docker-compose."
        )
    return pwd
