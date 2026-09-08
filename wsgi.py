"""Punto de entrada WSGI para servidores de producción.

Ejemplos de arranque:

    Linux / contenedor:
        gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 60 wsgi:app

    Windows:
        waitress-serve --listen=0.0.0.0:8000 wsgi:app

Variables de entorno:
    METAFLOTPY_ENTORNO      "produccion" activa cookies seguras, HSTS y caché
    METAFLOTPY_SECRET_KEY   obligatoria en producción
    METAFLOTPY_TRAS_PROXY   "1" si hay un proxy inverso delante (por defecto en producción)
"""

from app import crear_aplicacion

app = crear_aplicacion()
