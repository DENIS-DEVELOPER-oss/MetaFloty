"""Módulo II — Balance de masa de circuitos de molienda.

Resuelve la corriente desconocida a partir de las ecuaciones de conservación
del circuito y verifica el cierre del balance. No inventa valores por defecto:
si faltan datos lo indica en lugar de rellenarlos.
"""

import json

import plotly.graph_objs as go
import plotly.utils
from flask import Blueprint, render_template, request

from app.balance_masa.forms import CIRCUITOS, FormularioBalanceMasa

bp_balance_masa = Blueprint('balance_masa', __name__)

TOLERANCIA = 0.01     # t/h admitidos como error de redondeo al verificar el cierre


# --------------------------------------------------------------- definiciones

DEFINICIONES = {
    'directo': {
        'nombre': 'Circuito cerrado directo',
        'ecuacion': 'F = P + R',
        'campos': ['f_flujo', 'p_flujo', 'r_flujo'],
        'cc_formula': 'CC = (R / P) × 100 %',
        'descripcion': ('La alimentación fresca entra al molino; la descarga se clasifica y el '
                        'grueso retorna al molino. La carga circulante se mide respecto al producto.'),
    },
    'inverso': {
        'nombre': 'Circuito cerrado inverso',
        'ecuacion': 'F + R = P',
        'campos': ['f_flujo', 'p_flujo', 'r_flujo'],
        'cc_formula': 'CC = (R / F) × 100 %',
        'descripcion': ('La alimentación fresca se clasifica antes de moler; solo el grueso pasa al '
                        'molino. La carga circulante se mide respecto a la alimentación fresca.'),
    },
    'sabc1': {
        'nombre': 'Circuito SABC-1',
        'ecuacion': 'F = S ; S + R = B ; B = P + R  ⇒  F = P',
        'campos': ['f_flujo', 'p_flujo', 'r_flujo', 's_flujo', 'b_flujo'],
        'cc_formula': 'CC = (R / P) × 100 %',
        'descripcion': ('El SAG entrega todo su producto al molino de bolas, que trabaja en circuito '
                        'cerrado con el clasificador. En régimen estacionario el producto final iguala '
                        'a la alimentación fresca.'),
    },
    'sabc2': {
        'nombre': 'Circuito SABC-2',
        'ecuacion': 'F = S ; S = P + R ; R retorna como producto  ⇒  F = P + R',
        'campos': ['f_flujo', 'p_flujo', 'r_flujo', 's_flujo'],
        'cc_formula': 'CC = (R / P) × 100 %',
        'descripcion': ('La descarga del SAG pasa por un harnero: el fino es producto y el grueso '
                        '(pebbles) se muele aparte y se reincorpora al producto final.'),
    },
}


# --------------------------------------------------------------- utilidades

def _leer(form, campo):
    """Devuelve el valor del campo, o None si está vacío o no es positivo."""
    dato = getattr(form, campo).data
    if dato is None:
        return None
    try:
        v = float(dato)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _resolver_suma(a, b, c):
    """Resuelve a = b + c cuando falta exactamente una de las tres incógnitas.

    Devuelve (a, b, c, calculado) donde `calculado` indica cuál se dedujo,
    o None si no hay datos suficientes.
    """
    conocidos = sum(v is not None for v in (a, b, c))
    if conocidos < 2:
        return None
    if a is None:
        return b + c, b, c, 'a'
    if b is None:
        return a, a - c, c, 'b'
    if c is None:
        return a, b, a - b, 'c'
    return a, b, c, None      # los tres dados: solo se verifica


# --------------------------------------------------------------- cálculos

def calcular_directo(form):
    f, p, r = _leer(form, 'f_flujo'), _leer(form, 'p_flujo'), _leer(form, 'r_flujo')
    sol = _resolver_suma(f, p, r)
    if sol is None:
        return None, 'Ingresa al menos dos de las tres corrientes (F, P o R) para resolver la tercera.'
    f, p, r, calculado = sol
    if p < 0 or r < 0:
        return None, 'Los datos son incoherentes: la corriente deducida resulta negativa. Revisa que F sea mayor que P y que R.'

    error = f - (p + r)
    cc = (r / p * 100) if p > 0 else None
    return {
        'tipo': 'directo',
        'corrientes': [
            ('F', 'Alimentación fresca', f, calculado == 'a'),
            ('P', 'Producto final', p, calculado == 'b'),
            ('R', 'Carga circulante', r, calculado == 'c'),
        ],
        'f': f, 'p': p, 'r': r,
        'carga_circulante_pct': cc,
        'error_balance': error,
        'balance_ok': abs(error) <= TOLERANCIA,
        'pasos': [
            'Ecuación del circuito: F = P + R',
            _paso_despeje(calculado, 'F = P + R', ('F', 'P', 'R')),
            f'Sustituyendo: {f:,.2f} = {p:,.2f} + {r:,.2f}',
            f'Carga circulante: CC = ({r:,.2f} / {p:,.2f}) × 100 = {cc:,.1f} %' if cc is not None else 'Carga circulante no calculable (P = 0).',
        ],
        'sankey': [('Alimentación F', 'Molino', f), ('Molino', 'Clasificador', p + r),
                   ('Clasificador', 'Producto P', p), ('Clasificador', 'Molino (R)', r)],
    }, None


def calcular_inverso(form):
    f, p, r = _leer(form, 'f_flujo'), _leer(form, 'p_flujo'), _leer(form, 'r_flujo')
    # P = F + R  →  se resuelve como p = f + r
    sol = _resolver_suma(p, f, r)
    if sol is None:
        return None, 'Ingresa al menos dos de las tres corrientes (F, P o R) para resolver la tercera.'
    p, f, r, calculado = sol
    if f < 0 or r < 0:
        return None, 'Los datos son incoherentes: la corriente deducida resulta negativa. Revisa que P sea mayor que F y que R.'

    error = (f + r) - p
    cc = (r / f * 100) if f > 0 else None
    return {
        'tipo': 'inverso',
        'corrientes': [
            ('F', 'Alimentación fresca', f, calculado == 'b'),
            ('R', 'Carga circulante', r, calculado == 'c'),
            ('P', 'Producto del molino', p, calculado == 'a'),
        ],
        'f': f, 'p': p, 'r': r,
        'carga_circulante_pct': cc,
        'error_balance': error,
        'balance_ok': abs(error) <= TOLERANCIA,
        'pasos': [
            'Ecuación del circuito: F + R = P',
            _paso_despeje({'a': 'c', 'b': 'a', 'c': 'b'}.get(calculado), 'P = F + R', ('P', 'F', 'R')),
            f'Sustituyendo: {f:,.2f} + {r:,.2f} = {p:,.2f}',
            f'Carga circulante: CC = ({r:,.2f} / {f:,.2f}) × 100 = {cc:,.1f} %' if cc is not None else 'Carga circulante no calculable (F = 0).',
        ],
        'sankey': [('Alimentación F', 'Clasificador', f), ('Carga circulante R', 'Clasificador', r),
                   ('Clasificador', 'Molino', f + r), ('Molino', 'Producto P', p)],
    }, None


def calcular_sabc1(form):
    f = _leer(form, 'f_flujo')
    p = _leer(form, 'p_flujo')
    r = _leer(form, 'r_flujo')
    s = _leer(form, 's_flujo')
    b = _leer(form, 'b_flujo')

    # F = S y, en estado estacionario, P = F
    if f is None and s is not None:
        f = s
    if f is None and p is not None:
        f = p
    if f is None:
        return None, 'Ingresa la alimentación fresca F (o el producto del SAG S) para resolver el circuito SABC-1.'
    s = f
    p = f

    # B = P + R  y  S + R = B  (ambas dan el mismo R)
    if r is None and b is not None:
        r = b - p
    if r is None:
        return None, 'Ingresa la carga circulante R o la descarga del molino de bolas B para completar el balance.'
    if r < 0:
        return None, 'La descarga del molino de bolas B debe ser mayor que el producto final P.'
    b = p + r

    cc = (r / p * 100) if p > 0 else None
    error_bolas = (s + r) - b
    return {
        'tipo': 'sabc1',
        'corrientes': [
            ('F', 'Mineral fresco al SAG', f, False),
            ('S', 'Producto del SAG', s, True),
            ('B', 'Descarga del molino de bolas', b, True),
            ('P', 'Producto final', p, True),
            ('R', 'Carga circulante', r, False),
        ],
        'f': f, 'p': p, 'r': r, 's': s, 'b': b,
        'carga_circulante_pct': cc,
        'error_balance': error_bolas,
        'balance_ok': abs(error_bolas) <= TOLERANCIA,
        'pasos': [
            f'Balance del SAG: F = S  →  S = {s:,.2f} t/h',
            f'Estado estacionario global: P = F  →  P = {p:,.2f} t/h',
            f'Molino de bolas: S + R = B  →  {s:,.2f} + {r:,.2f} = {b:,.2f} t/h',
            f'Clasificador: B = P + R  →  {b:,.2f} = {p:,.2f} + {r:,.2f} t/h',
            f'Carga circulante: CC = ({r:,.2f} / {p:,.2f}) × 100 = {cc:,.1f} %' if cc is not None else '',
        ],
        'sankey': [('Mineral fresco F', 'Molino SAG', f), ('Molino SAG', 'Molino de bolas', s),
                   ('Carga circulante R', 'Molino de bolas', r), ('Molino de bolas', 'Clasificador', b),
                   ('Clasificador', 'Producto P', p), ('Clasificador', 'Carga circulante R', r)],
    }, None


def calcular_sabc2(form):
    f = _leer(form, 'f_flujo')
    p = _leer(form, 'p_flujo')
    r = _leer(form, 'r_flujo')
    s = _leer(form, 's_flujo')

    if f is None and s is not None:
        f = s
    if f is None:
        return None, 'Ingresa la alimentación fresca F (o el producto del SAG S) para resolver el circuito SABC-2.'
    s = f

    # Harnero: S = P + R
    sol = _resolver_suma(s, p, r)
    if sol is None:
        return None, 'Además de F, ingresa el producto del harnero P o el rechazo grueso R.'
    s, p, r, _ = sol
    if p < 0 or r < 0:
        return None, 'Los datos son incoherentes: P y R no pueden superar al producto del SAG S.'

    cc = (r / p * 100) if p > 0 else None
    error = s - (p + r)
    return {
        'tipo': 'sabc2',
        'corrientes': [
            ('F', 'Mineral fresco al SAG', f, False),
            ('S', 'Producto del SAG', s, True),
            ('P', 'Pasante del harnero', p, False),
            ('R', 'Rechazo grueso al molino de bolas', r, False),
        ],
        'f': f, 'p': p, 'r': r, 's': s,
        'carga_circulante_pct': cc,
        'error_balance': error,
        'balance_ok': abs(error) <= TOLERANCIA,
        'pasos': [
            f'Balance del SAG: F = S  →  S = {s:,.2f} t/h',
            f'Harnero: S = P + R  →  {s:,.2f} = {p:,.2f} + {r:,.2f} t/h',
            f'El rechazo R se muele y se reincorpora: producto total = P + R = {p + r:,.2f} t/h',
            f'Relación de rechazo: R/P = {cc:,.1f} %' if cc is not None else '',
        ],
        'sankey': [('Mineral fresco F', 'Molino SAG', f), ('Molino SAG', 'Harnero', s),
                   ('Harnero', 'Producto fino P', p), ('Harnero', 'Molino de bolas', r),
                   ('Molino de bolas', 'Producto fino P', r)],
    }, None


def _paso_despeje(calculado, ecuacion, simbolos):
    a, b, c = simbolos
    if calculado == 'a':
        return f'Se despeja {a}: {ecuacion}'
    if calculado == 'b':
        return f'Se despeja {b}: {b} = {a} − {c}'
    if calculado == 'c':
        return f'Se despeja {c}: {c} = {a} − {b}'
    return 'Las tres corrientes fueron ingresadas: el cálculo solo verifica el cierre del balance.'


CALCULADORES = {
    'directo': calcular_directo,
    'inverso': calcular_inverso,
    'sabc1': calcular_sabc1,
    'sabc2': calcular_sabc2,
}


# --------------------------------------------------------------- gráficos

def _fig(fig):
    return json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))


def grafico_sankey(resultados):
    """Diagrama de Sankey: el ancho de cada cinta es proporcional al flujo."""
    enlaces = [(o, d, v) for o, d, v in resultados['sankey'] if v and v > 0]
    if not enlaces:
        return None

    nodos = []
    for origen, destino, _ in enlaces:
        for n in (origen, destino):
            if n not in nodos:
                nodos.append(n)
    idx = {n: i for i, n in enumerate(nodos)}

    fig = go.Figure(go.Sankey(
        arrangement='snap',
        node=dict(label=nodos, pad=22, thickness=18,
                  line=dict(width=0.5, color='rgba(148,163,184,.6)')),
        link=dict(
            source=[idx[o] for o, _, _ in enlaces],
            target=[idx[d] for _, d, _ in enlaces],
            value=[round(v, 2) for _, _, v in enlaces],
            hovertemplate='%{source.label} → %{target.label}<br>%{value:.2f} t/h<extra></extra>',
        ),
    ))
    fig.update_layout(title='Diagrama de flujos del circuito (t/h)', margin=dict(l=10, r=10, t=52, b=20))
    return _fig(fig)


def grafico_corrientes(resultados):
    corrientes = resultados['corrientes']
    fig = go.Figure(go.Bar(
        x=[f'{s} · {n}' for s, n, _, _ in corrientes],
        y=[v for _, _, v, _ in corrientes],
        text=[f'{v:,.2f}' for _, _, v, _ in corrientes],
        textposition='outside',
        hovertemplate='%{x}<br>%{y:.2f} t/h<extra></extra>',
    ))
    fig.update_layout(
        title='Flujos másicos por corriente',
        xaxis=dict(title='Corriente'), yaxis=dict(title='Flujo (t/h)'),
        showlegend=False,
    )
    return _fig(fig)


def grafico_carga_circulante(resultados):
    """Indicador de carga circulante con las zonas operativas de referencia."""
    cc = resultados.get('carga_circulante_pct')
    if cc is None:
        return None
    maximo = max(500, cc * 1.2)
    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=cc,
        number={'suffix': ' %', 'valueformat': '.1f'},
        title={'text': 'Carga circulante'},
        gauge={
            'axis': {'range': [0, maximo]},
            'bar': {'color': '#0e7490', 'thickness': 0.7},
            'steps': [
                {'range': [0, 150], 'color': 'rgba(5,150,105,.18)'},
                {'range': [150, 350], 'color': 'rgba(217,119,6,.18)'},
                {'range': [350, maximo], 'color': 'rgba(220,38,38,.18)'},
            ],
            'threshold': {'line': {'color': '#ea580c', 'width': 3}, 'value': 250},
        },
    ))
    fig.update_layout(margin=dict(l=30, r=30, t=60, b=20))
    return _fig(fig)


def interpretar(resultados):
    cc = resultados.get('carga_circulante_pct')
    notas = []
    if cc is not None:
        if cc < 100:
            nivel, color = 'baja', 'info'
            comentario = ('Indica un clasificador muy eficiente o un molino sobredimensionado. '
                          'Revisa si el producto cumple la granulometría objetivo.')
        elif cc <= 350:
            nivel, color = 'dentro del rango habitual', 'success'
            comentario = ('Los circuitos industriales de molienda suelen operar entre 150 % y 350 % '
                          'de carga circulante.')
        else:
            nivel, color = 'alta', 'warning'
            comentario = ('Una recirculación elevada satura el molino y el sistema de bombeo. '
                          'Suele deberse a una clasificación deficiente o a un molino con capacidad insuficiente.')
        notas.append({
            'color': color,
            'texto': (f'La carga circulante es {cc:,.1f} %, {nivel}. {comentario} '
                      f'Por cada tonelada de producto se recirculan {cc / 100:,.2f} toneladas.')
        })

    if resultados.get('balance_ok'):
        notas.append({'color': 'success',
                      'texto': 'El balance de masa cierra correctamente: lo que entra al circuito iguala a lo que sale.'})
    else:
        notas.append({'color': 'danger',
                      'texto': (f'El balance no cierra: hay una diferencia de '
                                f'{abs(resultados["error_balance"]):,.3f} t/h entre las corrientes de entrada y salida. '
                                f'Revisa los valores ingresados.')})
    return notas


# --------------------------------------------------------------- vista

@bp_balance_masa.route('/', methods=['GET', 'POST'])
def balance_masa():
    formulario = FormularioBalanceMasa()
    contexto = {
        'formulario': formulario,
        'circuitos': CIRCUITOS,
        'definiciones': DEFINICIONES,
        'resultados': None,
        'graficos': {},
        'notas': [],
        'error_mensaje': None,
        'definicion': DEFINICIONES['directo'],
    }

    if request.method == 'POST':
        tipo = formulario.tipo_circuito.data or 'directo'
        contexto['definicion'] = DEFINICIONES.get(tipo, DEFINICIONES['directo'])

        calculador = CALCULADORES.get(tipo)
        if calculador is None:
            contexto['error_mensaje'] = 'Tipo de circuito no reconocido.'
        else:
            resultados, error = calculador(formulario)
            if error:
                contexto['error_mensaje'] = error
            else:
                contexto['resultados'] = resultados
                contexto['notas'] = interpretar(resultados)
                contexto['graficos'] = {
                    'sankey': grafico_sankey(resultados),
                    'corrientes': grafico_corrientes(resultados),
                    'carga': grafico_carga_circulante(resultados),
                }

    return render_template('balance_masa/balance.html', **contexto)
