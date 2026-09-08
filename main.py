"""Punto de entrada de MetaFlotPy.

Uso en desarrollo:
    python main.py

Variables de entorno reconocidas:
    METAFLOTPY_SECRET_KEY   clave de sesión (obligatoria en producción)
    METAFLOTPY_HOST         interfaz de escucha (por defecto 127.0.0.1)
    METAFLOTPY_PORT         puerto (por defecto 5000)
    METAFLOTPY_DEBUG        "1" para activar el modo depuración
"""

import os

from app import crear_aplicacion

app = crear_aplicacion()

if __name__ == '__main__':
    app.run(
        host=os.environ.get('METAFLOTPY_HOST', '127.0.0.1'),
        port=int(os.environ.get('METAFLOTPY_PORT', 5000)),
        debug=os.environ.get('METAFLOTPY_DEBUG', '1') == '1',
    )
