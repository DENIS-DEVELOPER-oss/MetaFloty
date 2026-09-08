"""Configuración de gunicorn para MetaFlotPy.

Uso:  gunicorn -c despliegue/linux/gunicorn.conf.py wsgi:app
"""

import os

# Escucha solo en localhost: Nginx es quien atiende el tráfico externo.
bind = os.environ.get('METAFLOTPY_BIND', '127.0.0.1:8000')

# Cada worker carga numpy, pandas, scipy y plotly: entre 200 y 300 MB de RSS.
# Por eso NO se usa la fórmula (2 × CPU + 1), que dispararía el consumo de
# memoria. Tres workers atienden con holgura el uso previsto; súbelo solo si
# el servidor tiene memoria de sobra.
workers = int(os.environ.get('METAFLOTPY_WORKERS', '3'))
threads = int(os.environ.get('METAFLOTPY_THREADS', '2'))
worker_class = 'gthread'

# Los cálculos más pesados (ajustes y gráficos) tardan menos de un segundo;
# 60 s deja margen de sobra y corta cualquier petición atascada.
timeout = 60
graceful_timeout = 30
keepalive = 5

# Reciclado periódico de workers: evita que una fuga lenta de memoria
# en las bibliotecas numéricas degrade el servicio.
max_requests = 500
max_requests_jitter = 50

# Precarga la aplicación antes de bifurcar: arranque más rápido y menos
# memoria gracias al copy-on-write de las bibliotecas numéricas.
preload_app = True

# Nginx es el único origen de confianza para las cabeceras X-Forwarded-*
forwarded_allow_ips = os.environ.get('METAFLOTPY_PROXY_IPS', '127.0.0.1')

accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('METAFLOTPY_LOG', 'info')
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms "%(a)s"'

proc_name = 'metaflotpy'
