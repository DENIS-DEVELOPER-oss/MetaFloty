"""MetaFlotPy — fábrica de la aplicación Flask."""

import logging
import os
from datetime import datetime

from flask import Flask, jsonify, render_template

VERSION = '2.0'

CLAVE_DESARROLLO = 'clave-desarrollo-metaflotpy'


def _es_verdadero(valor):
    return str(valor).strip().lower() in ('1', 'true', 'si', 'sí', 'yes', 'on')


def crear_aplicacion(config=None):
    app = Flask(__name__)

    entorno = os.environ.get('METAFLOTPY_ENTORNO', 'desarrollo').strip().lower()
    produccion = entorno in ('produccion', 'producción', 'production', 'prod')

    clave = os.environ.get('METAFLOTPY_SECRET_KEY', '').strip()
    if not clave:
        if produccion:
            raise RuntimeError(
                'Falta METAFLOTPY_SECRET_KEY. En producción la clave de sesión debe definirse '
                'como variable de entorno; genera una con:  python -c "import secrets; '
                'print(secrets.token_hex(32))"')
        clave = CLAVE_DESARROLLO

    app.config.update(
        SECRET_KEY=clave,
        ENTORNO=entorno,
        PRODUCCION=produccion,
        JSON_AS_ASCII=False,
        TEMPLATES_AUTO_RELOAD=not produccion,
        # Cachea estáticos 1 h en producción; el parámetro ?v= fuerza la recarga al publicar
        SEND_FILE_MAX_AGE_DEFAULT=3600 if produccion else 0,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,      # 2 MB: los formularios son pequeños
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=produccion,
        PREFERRED_URL_SCHEME='https' if produccion else 'http',
    )
    if config:
        app.config.update(config)

    if produccion:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    # Detrás de un proxy inverso (Nginx, Render, Railway…) se respetan las
    # cabeceras X-Forwarded-* para que url_for genere URLs https correctas.
    if _es_verdadero(os.environ.get('METAFLOTPY_TRAS_PROXY', '1' if produccion else '0')):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    _registrar_blueprints(app)
    _registrar_filtros(app)
    _registrar_contexto(app)
    _registrar_errores(app)
    _registrar_cabeceras(app)
    _registrar_salud(app)

    return app


def _registrar_salud(app):
    """Sonda de estado para el balanceador o el monitor de la plataforma."""

    @app.route('/salud')
    def salud():
        return jsonify({
            'estado': 'ok',
            'version': VERSION,
            'entorno': app.config.get('ENTORNO', 'desarrollo'),
        })


def _registrar_cabeceras(app):
    """Cabeceras de seguridad básicas."""

    @app.after_request
    def cabeceras(respuesta):
        respuesta.headers.setdefault('X-Content-Type-Options', 'nosniff')
        respuesta.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        respuesta.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        respuesta.headers.setdefault('Permissions-Policy',
                                     'geolocation=(), microphone=(), camera=()')
        if app.config.get('PRODUCCION'):
            respuesta.headers.setdefault(
                'Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return respuesta


def _registrar_blueprints(app):
    from app.principal.routes import bp_principal
    from app.tamizado.routes import bp_tamizado
    from app.balance_masa.routes import bp_balance_masa
    from app.balance_metalurgico.routes import bp_balance_metalurgico
    from app.dimensionamiento.routes import bp_dimensionamiento
    from app.valorizacion.routes import bp_valorizacion
    from app.utilitarios.routes import bp_utilitarios

    app.register_blueprint(bp_principal)
    app.register_blueprint(bp_tamizado, url_prefix='/tamizado')
    app.register_blueprint(bp_balance_masa, url_prefix='/balance-masa')
    app.register_blueprint(bp_balance_metalurgico, url_prefix='/balance-metalurgico')
    app.register_blueprint(bp_dimensionamiento, url_prefix='/dimensionamiento')
    app.register_blueprint(bp_valorizacion, url_prefix='/valorizacion')
    app.register_blueprint(bp_utilitarios, url_prefix='/utilitarios')


def _registrar_filtros(app):
    """Filtros Jinja para presentar números con formato peruano."""

    def _es_num(v):
        return isinstance(v, (int, float)) and v == v and v not in (float('inf'), float('-inf'))

    @app.template_filter('num')
    def filtro_num(valor, decimales=2):
        if not _es_num(valor):
            return '—'
        return f'{valor:,.{decimales}f}'.replace(',', '~').replace('.', ',').replace('~', '.')

    @app.template_filter('num_auto')
    def filtro_num_auto(valor):
        """Elige la cantidad de decimales según la magnitud del valor."""
        if not _es_num(valor):
            return '—'
        a = abs(valor)
        if a == 0:
            return '0'
        if a >= 1000:
            return filtro_num(valor, 1)
        if a >= 1:
            return filtro_num(valor, 3)
        if a >= 0.001:
            return filtro_num(valor, 4)
        return f'{valor:.3e}'

    @app.template_filter('usd')
    def filtro_usd(valor, decimales=2):
        if not _es_num(valor):
            return '—'
        return '$' + filtro_num(valor, decimales)


def _registrar_contexto(app):
    @app.context_processor
    def inyectar_globales():
        return {
            'version': VERSION,
            'anio': datetime.now().year,
        }


def _registrar_errores(app):
    @app.errorhandler(404)
    def no_encontrado(e):
        return render_template('errores/404.html'), 404

    @app.errorhandler(500)
    def error_interno(e):
        app.logger.exception('Error interno no controlado')
        return render_template('errores/500.html'), 500
