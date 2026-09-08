"""Módulo I — Análisis granulométrico.

Tres modelos sobre el mismo juego de datos de tamizado:
  · Gates-Gaudin-Schuhmann  %P = 100 (d/k)^n
  · Rosin-Rammler           R(d) = 100 e^[-(d/d0)^n]
  · Regresión empírica      %P = a·log(d) + b

Las vistas responden a POST devolviendo la página completa; la interfaz
sustituye solo el bloque de resultados, sin recargar (ver metaflotpy.js).
"""

import json
import math

import numpy as np
import pandas as pd
import plotly.graph_objs as go
import plotly.utils
from flask import Blueprint, render_template, request
from scipy import stats

bp_tamizado = Blueprint('tamizado', __name__)

# Serie de mallas ASTM habitual en laboratorio metalúrgico (abertura en mm)
MALLAS_ASTM = [
    ('1/2"', 12.700), ('3/8"', 9.525), ('1/4"', 6.350), ('N.º 4', 4.750),
    ('N.º 6', 3.350), ('N.º 8', 2.360), ('N.º 16', 1.180), ('N.º 20', 0.850),
    ('N.º 30', 0.600), ('N.º 40', 0.425), ('N.º 50', 0.300), ('N.º 70', 0.212),
    ('N.º 100', 0.150), ('N.º 140', 0.106), ('N.º 200', 0.075), ('N.º 270', 0.053),
    ('N.º 400', 0.038),
]

MALLAS_TYLER = [
    ('2,5 mesh', 8.000), ('3 mesh', 6.680), ('4 mesh', 4.699), ('6 mesh', 3.327),
    ('8 mesh', 2.362), ('10 mesh', 1.651), ('14 mesh', 1.168), ('20 mesh', 0.833),
    ('28 mesh', 0.589), ('35 mesh', 0.417), ('48 mesh', 0.295), ('65 mesh', 0.208),
    ('100 mesh', 0.147), ('150 mesh', 0.104), ('200 mesh', 0.074), ('270 mesh', 0.053),
    ('400 mesh', 0.037),
]


# ---------------------------------------------------------------- utilidades

def _leer_entrada():
    """Extrae peso total, aberturas y pesos retenidos del formulario.

    Devuelve (peso_total, aberturas, pesos, nombres, error) con error=None si
    los datos son utilizables.
    """
    aberturas_crudas = request.form.getlist('abertura[]')
    pesos_crudos = request.form.getlist('peso_retenido[]')
    nombres = request.form.getlist('nombre_malla[]')
    peso_total_crudo = request.form.get('peso_total', 0)

    def _f(v):
        try:
            return float(str(v).strip().replace(',', '.'))
        except (TypeError, ValueError):
            return None

    peso_total = _f(peso_total_crudo)

    filas = []
    for i, (a, p) in enumerate(zip(aberturas_crudas, pesos_crudos)):
        av, pv = _f(a), _f(p)
        if av is None or av <= 0:
            continue
        if pv is None or pv < 0:
            pv = 0.0
        nombre = nombres[i] if i < len(nombres) and nombres[i] else f'{av:g} mm'
        filas.append((av, pv, nombre))

    if len(filas) < 3:
        return None, None, None, None, 'Ingresa al menos 3 mallas con abertura y peso retenido válidos.'

    suma = sum(f[1] for f in filas)
    if suma <= 0:
        return None, None, None, None, 'La suma de los pesos retenidos debe ser mayor que cero.'

    # Si no se declaró peso total, se usa la suma de los retenidos
    if peso_total is None or peso_total <= 0:
        peso_total = suma

    filas.sort(key=lambda f: f[0], reverse=True)
    aberturas = [f[0] for f in filas]
    pesos = [f[1] for f in filas]
    nombres_ok = [f[2] for f in filas]
    return peso_total, aberturas, pesos, nombres_ok, None


def construir_tabla(aberturas, pesos, nombres, peso_total):
    """Tabla granulométrica base compartida por los tres modelos."""
    df = pd.DataFrame({'nombre': nombres, 'abertura': aberturas, 'peso_retenido': pesos})
    df['porcentaje_retenido'] = df['peso_retenido'] / peso_total * 100
    df['porcentaje_acumulado'] = df['porcentaje_retenido'].cumsum()
    df['porcentaje_pasante'] = (100 - df['porcentaje_acumulado']).clip(lower=0)
    df['R_d'] = df['porcentaje_acumulado']
    df['log_d'] = np.log10(df['abertura'])
    return df


def _interpolar_d(df, objetivo):
    """Tamaño d correspondiente a un % pasante dado (interpolación log-lineal).

    Devuelve None si el objetivo cae fuera del rango medido, para no inventar
    valores extrapolados.
    """
    d = df['abertura'].values[::-1]          # ascendente
    p = df['porcentaje_pasante'].values[::-1]
    if objetivo < p.min() or objetivo > p.max():
        return None
    for i in range(len(p) - 1):
        p1, p2 = p[i], p[i + 1]
        if p1 == p2:
            continue
        if min(p1, p2) <= objetivo <= max(p1, p2):
            d1, d2 = d[i], d[i + 1]
            if d1 <= 0 or d2 <= 0:
                continue
            # Interpolación lineal en log(d)
            frac = (objetivo - p1) / (p2 - p1)
            log_d = math.log10(d1) + frac * (math.log10(d2) - math.log10(d1))
            return 10 ** log_d
    return None


def descriptores(df, peso_total):
    """Percentiles característicos y coeficientes de uniformidad/curvatura."""
    percentiles = {}
    for objetivo in (10, 20, 25, 30, 50, 60, 75, 80, 90):
        percentiles[f'd{objetivo}'] = _interpolar_d(df, objetivo)

    d10, d30, d60 = percentiles['d10'], percentiles['d30'], percentiles['d60']
    cu = (d60 / d10) if (d10 and d60 and d10 > 0) else None
    cc = (d30 ** 2 / (d10 * d60)) if (d10 and d30 and d60 and d10 * d60 > 0) else None

    suma_retenidos = float(df['peso_retenido'].sum())
    error_masa = peso_total - suma_retenidos
    error_pct = (abs(error_masa) / peso_total * 100) if peso_total else 0

    if cu is None:
        clasificacion = 'No determinable con el rango medido'
    elif cu < 4:
        clasificacion = 'Material muy uniforme (mal graduado)'
    elif cu < 6:
        clasificacion = 'Uniformidad media'
    else:
        clasificacion = 'Material bien graduado (amplio rango de tamaños)'

    return {
        **percentiles,
        'cu': cu,
        'cc': cc,
        'clasificacion': clasificacion,
        'peso_total': peso_total,
        'suma_retenidos': suma_retenidos,
        'error_masa': error_masa,
        'error_masa_pct': error_pct,
        'masa_ok': error_pct <= 1.0,
        'n_mallas': int(len(df)),
        'rango_min': float(df['abertura'].min()),
        'rango_max': float(df['abertura'].max()),
    }


def _fig(fig):
    return json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))


def _calidad(r2):
    if r2 is None:
        return ('—', 'secondary')
    if r2 >= 0.99:
        return ('Ajuste excelente', 'success')
    if r2 >= 0.95:
        return ('Ajuste muy bueno', 'success')
    if r2 >= 0.90:
        return ('Ajuste aceptable', 'warning')
    return ('Ajuste pobre: revisa los datos', 'danger')


# ------------------------------------------------------------ curva base

def grafico_curvas(df, ajuste=None, etiqueta_ajuste=''):
    """Curvas de pasante y retenido acumulado, con el modelo ajustado encima."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['abertura'], y=df['porcentaje_pasante'],
        mode='markers+lines', name='% Pasante acumulado',
        marker=dict(size=8), line=dict(width=2.5),
        hovertemplate='d = %{x:.4g} mm<br>%Pasante = %{y:.2f} %<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=df['abertura'], y=df['porcentaje_acumulado'],
        mode='markers+lines', name='% Retenido acumulado',
        marker=dict(size=7), line=dict(width=2, dash='dot'),
        hovertemplate='d = %{x:.4g} mm<br>%Retenido = %{y:.2f} %<extra></extra>',
    ))
    if ajuste is not None:
        fig.add_trace(go.Scatter(
            x=ajuste[0], y=ajuste[1], mode='lines',
            name=etiqueta_ajuste or 'Modelo ajustado',
            line=dict(width=2.5, dash='dash'),
            hovertemplate='d = %{x:.4g} mm<br>modelo = %{y:.2f} %<extra></extra>',
        ))
    fig.update_layout(
        title='Curva granulométrica',
        xaxis=dict(title='Abertura d (mm)', type='log'),
        yaxis=dict(title='Porcentaje acumulado (%)', range=[0, 102]),
        hovermode='x unified',
    )
    return _fig(fig)


def grafico_barras_retenido(df):
    """Distribución del retenido parcial por malla."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[str(n) for n in df['nombre']], y=df['porcentaje_retenido'],
        name='% Retenido parcial',
        text=[f'{v:.1f}%' for v in df['porcentaje_retenido']],
        textposition='outside',
        hovertemplate='%{x}<br>Retenido = %{y:.2f} %<extra></extra>',
    ))
    fig.update_layout(
        title='Distribución del retenido parcial por malla',
        xaxis=dict(title='Malla'),
        yaxis=dict(title='% Retenido'),
        showlegend=False,
    )
    return _fig(fig)


# ============================================================ GGS

def modelo_ggs(df):
    """Ajusta %P = 100 (d/k)^n mediante regresión log-log."""
    v = df[(df['porcentaje_pasante'] > 0.05) & (df['porcentaje_pasante'] < 99.95)]
    if len(v) < 2:
        return None

    log_d = np.log10(v['abertura'].values)
    log_p = np.log10(v['porcentaje_pasante'].values)
    reg = stats.linregress(log_d, log_p)
    n = float(reg.slope)
    b = float(reg.intercept)
    r2 = float(reg.rvalue ** 2)

    # log(%P) = n·log(d) + b ; %P = 100 cuando d = k  →  k = 10^((2-b)/n)
    k = 10 ** ((2 - b) / n) if abs(n) > 1e-12 else None

    tabla_log = [{
        'nombre': r['nombre'], 'abertura': float(r['abertura']),
        'porcentaje_pasante': float(r['porcentaje_pasante']),
        'log_di': float(np.log10(r['abertura'])),
        'log_Pi': float(np.log10(r['porcentaje_pasante'])),
        'log_Pi_calc': float(n * np.log10(r['abertura']) + b),
    } for _, r in v.iterrows()]

    texto, color = _calidad(r2)
    return {
        'n': n, 'k': k, 'b': b, 'r2': r2,
        'err_std': float(reg.stderr),
        'ecuacion': f'log(%P) = {n:.4f}·log(d) + {b:.4f}',
        'ecuacion_modelo': (f'%P = 100 · (d / {k:.4f})^{n:.4f}' if k else '—'),
        'calidad': texto, 'calidad_color': color,
        'tabla_logaritmos': tabla_log,
        'interpretacion': (
            f'El exponente n = {n:.3f} describe la pendiente de la distribución: '
            + ('valores bajos (n < 0,5) indican un material de granulometría amplia. '
               if n < 0.5 else
               'valores altos (n > 1) indican una distribución estrecha, con tamaños concentrados. '
               if n > 1 else
               'un valor cercano a 0,5–1 corresponde a una distribución típica de molienda. ')
            + (f'El módulo de tamaño k = {k:.4f} mm es el tamaño teórico al 100 % pasante.' if k else '')
        ),
    }


def grafico_log_log(df, modelo):
    v = df[(df['porcentaje_pasante'] > 0.05) & (df['porcentaje_pasante'] < 99.95)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=v['abertura'], y=v['porcentaje_pasante'],
        mode='markers', name='Datos experimentales', marker=dict(size=11),
        hovertemplate='d = %{x:.4g} mm<br>%P = %{y:.2f} %<extra></extra>',
    ))
    if modelo:
        d = np.logspace(np.log10(v['abertura'].min()), np.log10(v['abertura'].max()), 60)
        p = 10 ** (modelo['n'] * np.log10(d) + modelo['b'])
        fig.add_trace(go.Scatter(
            x=d, y=np.clip(p, 0.01, 100), mode='lines',
            name=f"Recta GGS (R² = {modelo['r2']:.4f})", line=dict(width=2.5, dash='dash'),
        ))
    fig.update_layout(
        title='Linealización log-log · pendiente = n',
        xaxis=dict(title='log d (mm)', type='log'),
        yaxis=dict(title='log %P (%)', type='log'),
    )
    return _fig(fig)


@bp_tamizado.route('/', methods=['GET'])
def index():
    return render_template('tamizado/index.html', mallas_astm=MALLAS_ASTM, mallas_tyler=MALLAS_TYLER)


@bp_tamizado.route('/analisis', methods=['GET', 'POST'])
def analisis_granulometrico():
    contexto = _contexto_base()

    if request.method == 'POST':
        peso_total, aberturas, pesos, nombres, error = _leer_entrada()
        if error:
            return _responder_error(error, 'tamizado/analisis.html', contexto)

        df = construir_tabla(aberturas, pesos, nombres, peso_total)
        modelo = modelo_ggs(df)
        ajuste = None
        if modelo:
            d = np.logspace(np.log10(df['abertura'].min()), np.log10(df['abertura'].max()), 60)
            ajuste = (d.tolist(), np.clip(10 ** (modelo['n'] * np.log10(d) + modelo['b']), 0, 100).tolist())

        payload = {
            'tabla_datos': _tabla_json(df),
            'resultados_calculo': modelo,
            'descriptores': descriptores(df, peso_total),
            'grafico_principal': grafico_curvas(df, ajuste, 'Modelo GGS ajustado'),
            'grafico_log_log': grafico_log_log(df, modelo),
            'grafico_barras': grafico_barras_retenido(df),
        }
        contexto.update(payload)

    return render_template('tamizado/analisis.html', **contexto)


# ============================================================ Rosin-Rammler

def modelo_rosin_rammler(df):
    """Ajusta R(d) = 100 e^[-(d/d0)^n] linealizando con ln[-ln(R/100)]."""
    v = df[(df['R_d'] > 0.05) & (df['R_d'] < 99.95)]
    if len(v) < 2:
        return None

    ln_d, ln_ln_r, tabla = [], [], []
    for _, r in v.iterrows():
        frac = r['R_d'] / 100
        if not (0 < frac < 1):
            continue
        x = float(np.log(r['abertura']))
        y = float(np.log(-np.log(frac)))
        ln_d.append(x)
        ln_ln_r.append(y)
        tabla.append({
            'nombre': r['nombre'], 'abertura': float(r['abertura']),
            'R_d': float(r['R_d']), 'ln_d': x, 'ln_ln_R': y,
        })

    if len(ln_d) < 2:
        return None

    reg = stats.linregress(ln_d, ln_ln_r)
    n = float(reg.slope)
    if abs(n) < 1e-12:
        return None
    d0 = float(np.exp(-reg.intercept / n))
    r2 = float(reg.rvalue ** 2)

    for fila in tabla:
        fila['ln_ln_R_calc'] = n * fila['ln_d'] + float(reg.intercept)

    # d63,2 es por definición d0 (R = 100/e ≈ 36,8 % retenido)
    texto, color = _calidad(r2)
    return {
        'n': n, 'd0': d0, 'r2': r2, 'intercepto': float(reg.intercept),
        'formula_rosin': f'R(d) = 100 · e^[−(d / {d0:.4f})^{n:.4f}]',
        'ecuacion_lineal': f'ln[−ln(R/100)] = {n:.4f}·ln(d) − {n * np.log(d0):.4f}',
        'calidad': texto, 'calidad_color': color,
        'tabla_logaritmos': tabla,
        'd632': d0,
        'interpretacion': (
            f'd₀ = {d0:.4f} mm es el tamaño característico: por debajo de él pasa el 63,2 % del material. '
            f'El módulo de uniformidad n = {n:.3f} indica '
            + ('una distribución muy estrecha (partículas de tamaño homogéneo).' if n > 1.5 else
               'una distribución amplia, típica de molienda convencional.' if n < 0.8 else
               'una distribución de amplitud moderada.')
        ),
    }


def grafico_rr_ajuste(df, modelo):
    v = df[(df['R_d'] > 0.05) & (df['R_d'] < 99.95)]
    fig = go.Figure()
    if modelo:
        x = np.log(v['abertura'].values)
        y = np.log(-np.log(v['R_d'].values / 100))
        fig.add_trace(go.Scatter(
            x=x, y=y, mode='markers', name='Datos linealizados', marker=dict(size=11),
            hovertemplate='ln(d) = %{x:.3f}<br>ln[−ln(R/100)] = %{y:.3f}<extra></extra>',
        ))
        xl = np.linspace(x.min(), x.max(), 40)
        fig.add_trace(go.Scatter(
            x=xl, y=modelo['n'] * xl + modelo['intercepto'], mode='lines',
            name=f"Recta ajustada (R² = {modelo['r2']:.4f})", line=dict(width=2.5, dash='dash'),
        ))
    fig.update_layout(
        title='Linealización Rosin-Rammler · pendiente = n',
        xaxis=dict(title='ln(d)'),
        yaxis=dict(title='ln[−ln(R(d)/100)]'),
    )
    return _fig(fig)


@bp_tamizado.route('/rosin-rammler', methods=['GET', 'POST'])
def rosin_rammler():
    contexto = _contexto_base()

    if request.method == 'POST':
        peso_total, aberturas, pesos, nombres, error = _leer_entrada()
        if error:
            return _responder_error(error, 'tamizado/rosin_rammler.html', contexto)

        df = construir_tabla(aberturas, pesos, nombres, peso_total)
        modelo = modelo_rosin_rammler(df)
        ajuste = None
        if modelo:
            d = np.logspace(np.log10(df['abertura'].min()), np.log10(df['abertura'].max()), 60)
            r = 100 * np.exp(-((d / modelo['d0']) ** modelo['n']))
            ajuste = (d.tolist(), (100 - r).tolist())   # se grafica como % pasante

        payload = {
            'tabla_datos': _tabla_json(df),
            'resultados_calculo': modelo,
            'descriptores': descriptores(df, peso_total),
            'grafico_principal': grafico_curvas(df, ajuste, 'Modelo Rosin-Rammler'),
            'grafico_semilog': grafico_rr_ajuste(df, modelo),
            'grafico_barras': grafico_barras_retenido(df),
        }
        contexto.update(payload)

    return render_template('tamizado/rosin_rammler.html', **contexto)


# ============================================================ Regresión empírica

def modelo_regresion(df):
    """Mínimos cuadrados de %P frente a log(d), con detalle del cálculo."""
    v = df[(df['porcentaje_pasante'] > 0) & (df['porcentaje_pasante'] <= 100)]
    if len(v) < 2:
        return None

    x = v['log_d'].values
    y = v['porcentaje_pasante'].values
    n = len(x)

    sum_x, sum_y = float(np.sum(x)), float(np.sum(y))
    sum_xy, sum_x2 = float(np.sum(x * y)), float(np.sum(x ** 2))
    denom = n * sum_x2 - sum_x ** 2
    if abs(denom) < 1e-12:
        return None

    a = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - a * sum_x) / n

    y_pred = a * x + b
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse = float(np.sqrt(ss_res / n))
    residuo_max = float(np.max(np.abs(y - y_pred)))

    tabla = [{
        'nombre': r['nombre'], 'abertura': float(r['abertura']),
        'porcentaje_pasante': float(r['porcentaje_pasante']),
        'log_d': float(r['log_d']),
        'y_calculado': float(a * r['log_d'] + b),
        'residuo': float(r['porcentaje_pasante'] - (a * r['log_d'] + b)),
    } for _, r in v.iterrows()]

    texto, color = _calidad(r2)
    return {
        'a': a, 'b': b, 'r2': r2, 'rmse': rmse, 'residuo_max': residuo_max,
        'n_datos': n, 'sum_x': sum_x, 'sum_y': sum_y, 'sum_xy': sum_xy, 'sum_x2': sum_x2,
        'ecuacion': f'%P = {a:.4f}·log(d) + {b:.4f}',
        'calidad': texto, 'calidad_color': color,
        'tabla_regresion': tabla,
        'formula_minimos_cuadrados': {
            'a_formula': 'a = (n·Σxy − Σx·Σy) / (n·Σx² − (Σx)²)',
            'b_formula': 'b = (Σy − a·Σx) / n',
        },
        'interpretacion': (
            f'Por cada década de aumento del tamaño (×10 en d), el porcentaje pasante '
            f'{"aumenta" if a > 0 else "disminuye"} {abs(a):.2f} puntos porcentuales. '
            f'El modelo explica el {r2 * 100:.1f} % de la variabilidad observada '
            f'(RMSE = {rmse:.2f} puntos).'
        ),
    }


def grafico_dispersion(df, modelo):
    v = df[(df['porcentaje_pasante'] > 0) & (df['porcentaje_pasante'] <= 100)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=v['log_d'], y=v['porcentaje_pasante'], mode='markers',
        name='Datos experimentales', marker=dict(size=12),
        text=[f'{r["nombre"]} · d = {r["abertura"]:.4g} mm' for _, r in v.iterrows()],
        hovertemplate='<b>%{text}</b><br>log d = %{x:.3f}<br>%P = %{y:.2f} %<extra></extra>',
    ))
    if modelo:
        xl = np.linspace(v['log_d'].min(), v['log_d'].max(), 40)
        fig.add_trace(go.Scatter(
            x=xl, y=modelo['a'] * xl + modelo['b'], mode='lines',
            name=f"Recta ajustada (R² = {modelo['r2']:.4f})", line=dict(width=2.5, dash='dash'),
        ))
    fig.update_layout(
        title='Dispersión y recta de mínimos cuadrados',
        xaxis=dict(title='log(d)'),
        yaxis=dict(title='% Pasante acumulado'),
    )
    return _fig(fig)


def grafico_residuos(modelo):
    if not modelo:
        return None
    tabla = modelo['tabla_regresion']
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[f['log_d'] for f in tabla], y=[f['residuo'] for f in tabla],
        name='Residuo',
        hovertemplate='log d = %{x:.3f}<br>residuo = %{y:.2f} pp<extra></extra>',
    ))
    fig.add_hline(y=0, line_dash='dash', line_width=1.5)
    fig.update_layout(
        title='Residuos del ajuste (observado − calculado)',
        xaxis=dict(title='log(d)'), yaxis=dict(title='Residuo (puntos porcentuales)'),
        showlegend=False,
    )
    return _fig(fig)


@bp_tamizado.route('/regresion-lineal', methods=['GET', 'POST'])
def regresion_lineal():
    contexto = _contexto_base()

    if request.method == 'POST':
        peso_total, aberturas, pesos, nombres, error = _leer_entrada()
        if error:
            return _responder_error(error, 'tamizado/regresion_lineal.html', contexto)

        df = construir_tabla(aberturas, pesos, nombres, peso_total)
        modelo = modelo_regresion(df)
        ajuste = None
        if modelo:
            d = np.logspace(np.log10(df['abertura'].min()), np.log10(df['abertura'].max()), 60)
            ajuste = (d.tolist(), np.clip(modelo['a'] * np.log10(d) + modelo['b'], 0, 100).tolist())

        payload = {
            'tabla_datos': _tabla_json(df),
            'resultados_calculo': modelo,
            'descriptores': descriptores(df, peso_total),
            'grafico_principal': grafico_curvas(df, ajuste, 'Recta empírica'),
            'grafico_regresion': grafico_dispersion(df, modelo),
            'grafico_residuos': grafico_residuos(modelo),
        }
        contexto.update(payload)

    return render_template('tamizado/regresion_lineal.html', **contexto)


# ---------------------------------------------------------------- auxiliares

def _contexto_base():
    return {
        'mallas_astm': MALLAS_ASTM,
        'mallas_tyler': MALLAS_TYLER,
        'tabla_datos': None,
        'resultados_calculo': None,
        'descriptores': None,
        'grafico_principal': None,
        'grafico_log_log': None,
        'grafico_semilog': None,
        'grafico_regresion': None,
        'grafico_residuos': None,
        'grafico_barras': None,
        'error_mensaje': None,
    }


def _tabla_json(df):
    columnas = ['nombre', 'abertura', 'peso_retenido', 'porcentaje_retenido',
                'porcentaje_acumulado', 'porcentaje_pasante']
    return df[columnas].to_dict('records')


def _responder_error(mensaje, plantilla, contexto):
    contexto['error_mensaje'] = mensaje
    return render_template(plantilla, **contexto)
