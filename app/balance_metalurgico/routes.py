"""Módulo III — Balance metalúrgico.

Concilia el balance de masa (F = ΣC + T) con el balance de metal
(F·f = ΣC·c + T·t) y entrega recuperación, razón de concentración y
distribución del metal por producto.

Ley de cabeza
-------------
En planta conviven dos valores para la ley de la alimentación:

  · **Ensayada**  — resultado del análisis químico de la muestra de cabeza.
                    Es una medición independiente, sujeta a error de muestreo.
  · **Calculada** — reconstituida a partir de los productos:
                    f_calc = (ΣC·c + T·t) / F

La práctica habitual es informar los resultados sobre la **ley de cabeza
calculada**, porque hace que el balance cierre exactamente y evita
recuperaciones superiores al 100 %. La diferencia entre ambas es el
indicador de control de calidad del muestreo y del análisis.

Con un solo concentrado y las tres leyes conocidas aplica la fórmula de dos
productos, que resuelve las masas sin necesidad de pesarlas:
        C/F = (f − t) / (c − t)
"""

import json

import numpy as np
import plotly.graph_objs as go
import plotly.utils
from flask import Blueprint, render_template, request

from app.balance_metalurgico.forms import UNIDADES_LEY, FormularioBalanceMetalurgico

bp_balance_metalurgico = Blueprint('balance_metalurgico', __name__)

TOLERANCIA_MASA = 0.01
# Desviación relativa admisible entre la ley de cabeza ensayada y la calculada
TOLERANCIA_CABEZA_PCT = 5.0

N_CONCENTRADOS = {'1_concentrado': 1, '2_concentrados': 2, '3_concentrados': 3}


def _v(campo):
    """Valor positivo del campo, o None si está vacío o es cero."""
    d = campo.data
    if d is None:
        return None
    try:
        x = float(d)
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def calcular(formulario):
    """Resuelve el balance y devuelve (resultados, error)."""
    tipo = formulario.tipo_balance.data or '1_concentrado'
    n = N_CONCENTRADOS.get(tipo, 1)
    unidad = formulario.unidad_ley.data or '%'
    base_ley = formulario.base_ley.data or 'calculada'

    F = _v(formulario.f_masa)
    f_ensayada = _v(formulario.f_ley)
    T = _v(formulario.t_masa)
    t = formulario.t_ley.data          # el relave puede tener ley 0 legítimamente
    t = float(t) if t is not None else None

    concentrados = []
    for i in range(1, n + 1):
        concentrados.append({
            'idx': i,
            'masa': _v(getattr(formulario, f'c{i}_masa')),
            'ley': _v(getattr(formulario, f'c{i}_ley')),
        })

    for c in concentrados:
        if c['ley'] is None:
            return None, f'Falta la ley del concentrado {c["idx"]} (c{c["idx"]}).'

    metodo = None
    metodo_masas = 'directo'
    t_derivada = False

    # ---- Fórmula de dos productos: un concentrado con las tres leyes ----
    if n == 1 and t is not None and concentrados[0]['masa'] is None and T is None:
        if f_ensayada is None:
            return None, ('Para resolver las masas con la fórmula de dos productos hace falta la '
                          'ley de cabeza ensayada. Ingrésala, o bien indica las masas de los productos '
                          'para que la ley de cabeza se calcule a partir de ellos.')
        c1 = concentrados[0]['ley']
        if abs(c1 - t) < 1e-9:
            return None, 'La ley del concentrado y la del relave son iguales: no hay separación que calcular.'
        if not (min(c1, t) <= f_ensayada <= max(c1, t)):
            return None, ('La ley de cabeza debe quedar entre la del relave y la del concentrado '
                          f'({t:g} ≤ f ≤ {c1:g}). Revisa los valores ingresados.')
        if F is None:
            F = 100.0
            metodo = ('Sin masa de alimentación se tomó F = 100 como base de cálculo: '
                      'las masas resultantes son porcentajes de la alimentación.')
        razon = (f_ensayada - t) / (c1 - t)
        concentrados[0]['masa'] = F * razon
        T = F - concentrados[0]['masa']
        metodo_masas = 'dos_productos'
        if metodo is None:
            metodo = 'Masas obtenidas con la fórmula de dos productos C/F = (f − t)/(c − t).'

    # ---- Cierre del balance de masa ----
    masas = [c['masa'] for c in concentrados] + [T]
    faltantes = [i for i, m in enumerate(masas) if m is None]

    if F is None:
        if faltantes:
            return None, ('Faltan datos de masa. Ingresa la alimentación F y las masas de los productos, '
                          'dejando en blanco solo la que quieres calcular.')
        F = sum(masas)
        metodo = metodo or 'La alimentación F se obtuvo sumando las masas de los productos.'
    elif len(faltantes) == 1:
        idx = faltantes[0]
        masas[idx] = F - sum(m for m in masas if m is not None)
        if masas[idx] < 0:
            return None, ('La masa deducida resulta negativa: la suma de los productos ingresados '
                          'supera a la alimentación F.')
        nombre = 'el relave T' if idx == len(masas) - 1 else f'el concentrado {idx + 1}'
        metodo = metodo or f'Se dedujo la masa de {nombre} a partir de F = ΣC + T.'
        metodo_masas = 'balance_masa'
    elif len(faltantes) > 1:
        return None, ('Hay más de una masa desconocida. Deja en blanco solo una de ellas, '
                      'o usa un concentrado con las tres leyes para aplicar la fórmula de dos productos.')

    for i, c in enumerate(concentrados):
        c['masa'] = masas[i]
    T = masas[-1]

    metal_conc_total = sum(c['masa'] * c['ley'] for c in concentrados)

    # ---- Ley de relave por diferencia, si no se declaró ----
    if t is None:
        if f_ensayada is None:
            return None, ('Falta la ley del relave (t). Puedes dejarla en blanco solo si ingresas la '
                          'ley de cabeza ensayada, para deducirla del balance de metal.')
        if T and T > 0:
            t = (F * f_ensayada - metal_conc_total) / T
            t_derivada = True
            metodo = (metodo or '') + ' La ley de relave se dedujo del balance de metal.'
        else:
            t = 0.0

    metal_relave = T * t
    metal_salida = metal_conc_total + metal_relave

    # ================= LEY DE CABEZA =================
    # Reconstituida a partir de los productos: siempre cierra el balance.
    f_calculada = (metal_salida / F) if F else None

    # La comparación entre ambas leyes solo es informativa cuando la calculada
    # NO se dedujo a partir de la ensayada (fórmula de dos productos o ley de
    # relave por diferencia): en esos casos ambas coinciden por construcción.
    cabeza_independiente = (metodo_masas != 'dos_productos') and (not t_derivada)

    if f_ensayada is None:
        base_ley = 'calculada'
    f_usada = f_calculada if base_ley == 'calculada' else f_ensayada

    if not f_usada or f_usada <= 0:
        return None, ('No se pudo determinar la ley de cabeza: revisa las leyes y masas de los '
                      'productos, o ingresa la ley de cabeza ensayada.')

    dif_cabeza_abs = dif_cabeza_rel = None
    if f_ensayada and f_calculada and cabeza_independiente:
        dif_cabeza_abs = f_calculada - f_ensayada
        dif_cabeza_rel = dif_cabeza_abs / f_ensayada * 100

    metal_alim = F * f_usada

    # Recuperación bajo ambas bases, para poder compararlas
    rec_calculada = (metal_conc_total / metal_salida * 100) if metal_salida else None
    rec_ensayada = (metal_conc_total / (F * f_ensayada) * 100) if f_ensayada else None

    # ---- Indicadores por producto ----
    productos = []
    for c in concentrados:
        metal = c['masa'] * c['ley']
        productos.append({
            'simbolo': f'C{c["idx"]}' if len(concentrados) > 1 else 'C',
            'nombre': f'Concentrado {c["idx"]}' if len(concentrados) > 1 else 'Concentrado',
            'masa': c['masa'],
            'ley': c['ley'],
            'metal': metal,
            'recuperacion': (metal / metal_alim * 100) if metal_alim else None,
            'rendimiento_masa': (c['masa'] / F * 100) if F else None,
            'ratio': (F / c['masa']) if c['masa'] else None,
            'enriquecimiento': (c['ley'] / f_usada) if f_usada else None,
            'es_concentrado': True,
        })

    productos.append({
        'simbolo': 'T', 'nombre': 'Relave', 'masa': T, 'ley': t, 'metal': metal_relave,
        'recuperacion': (metal_relave / metal_alim * 100) if metal_alim else None,
        'rendimiento_masa': (T / F * 100) if F else None,
        'ratio': None, 'enriquecimiento': (t / f_usada) if f_usada else None,
        'es_concentrado': False,
    })

    recuperacion_total = sum(p['recuperacion'] or 0 for p in productos if p['es_concentrado'])
    masa_conc_total = sum(p['masa'] for p in productos if p['es_concentrado'])

    error_masa = F - (masa_conc_total + T)
    # El desbalance de metal es exactamente la discrepancia de la ley de cabeza
    error_metal = (F * f_ensayada - metal_salida) if f_ensayada else 0.0

    etiqueta_base = ('calculada' if base_ley == 'calculada' else 'ensayada')

    pasos = [
        f'Balance de masa: F = ΣC + T  →  {F:,.2f} = {masa_conc_total:,.2f} + {T:,.2f}',
        f'Metal en concentrados: ΣC·c = {metal_conc_total:,.2f}',
        f'Metal en relave: T·t = {T:,.2f} × {t:,.4g} = {metal_relave:,.2f}',
        f'Ley de cabeza calculada: f_calc = (ΣC·c + T·t) / F = {metal_salida:,.2f} / {F:,.2f} = '
        f'{f_calculada:,.4g} {unidad}',
    ]
    if f_ensayada:
        pasos.append(f'Ley de cabeza ensayada: f_ens = {f_ensayada:,.4g} {unidad}')
    pasos.append(f'Base adoptada para los resultados: ley de cabeza {etiqueta_base} = '
                 f'{f_usada:,.4g} {unidad}')
    pasos.append(f'Metal alimentado: F·f = {F:,.2f} × {f_usada:,.4g} = {metal_alim:,.2f}')
    pasos.append(f'Recuperación global: R = ({metal_conc_total:,.2f} / {metal_alim:,.2f}) × 100 = '
                 f'{recuperacion_total:,.2f} %')
    if masa_conc_total > 0:
        pasos.append(f'Razón de concentración: K = F / ΣC = {F:,.2f} / {masa_conc_total:,.2f} = '
                     f'{F / masa_conc_total:,.2f}')

    return {
        'tipo': tipo, 'n_concentrados': n, 'unidad': unidad,
        'F': F, 'T': T, 't': t,
        # Ley de cabeza
        'f_ensayada': f_ensayada,
        'f_calculada': f_calculada,
        'f_usada': f_usada,
        'f': f_usada,                       # compatibilidad con el resto de la vista
        'base_ley': base_ley,
        'etiqueta_base': etiqueta_base,
        'cabeza_independiente': cabeza_independiente,
        'dif_cabeza_abs': dif_cabeza_abs,
        'dif_cabeza_rel': dif_cabeza_rel,
        'cabeza_ok': (dif_cabeza_rel is None or abs(dif_cabeza_rel) <= TOLERANCIA_CABEZA_PCT),
        'rec_calculada': rec_calculada,
        'rec_ensayada': rec_ensayada,
        # Resultados
        'productos': productos,
        'metal_alimentacion': metal_alim,
        'metal_relave': metal_relave,
        'metal_salida': metal_salida,
        'masa_concentrados': masa_conc_total,
        'recuperacion_total': recuperacion_total,
        'ratio_concentracion': (F / masa_conc_total) if masa_conc_total else None,
        'enriquecimiento_global': ((metal_conc_total / masa_conc_total) / f_usada)
                                  if masa_conc_total and f_usada else None,
        'rendimiento_masa': (masa_conc_total / F * 100) if F else None,
        'error_masa': error_masa,
        'error_metal': error_metal,
        'balance_masa_ok': abs(error_masa) <= TOLERANCIA_MASA,
        'metodo': (metodo or 'Balance resuelto con las masas y leyes ingresadas.').strip(),
        'pasos': pasos,
    }, None


# --------------------------------------------------------------- gráficos

def _fig(fig):
    return json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))


def grafico_sankey_metal(r):
    """Reparto del metal contenido entre concentrados y relave."""
    etiquetas = ['Alimentación (F·f)'] + [f"{p['simbolo']} ({p['nombre']})" for p in r['productos']]
    fuentes, destinos, valores = [], [], []
    for i, p in enumerate(r['productos'], start=1):
        if p['metal'] and p['metal'] > 0:
            fuentes.append(0)
            destinos.append(i)
            valores.append(round(p['metal'], 3))
    if not valores:
        return None

    fig = go.Figure(go.Sankey(
        node=dict(label=etiquetas, pad=24, thickness=18,
                  line=dict(width=0.5, color='rgba(148,163,184,.6)')),
        link=dict(source=fuentes, target=destinos, value=valores,
                  hovertemplate='%{target.label}<br>Metal: %{value:.2f}<extra></extra>'),
    ))
    fig.update_layout(title='Reparto del metal contenido', margin=dict(l=10, r=10, t=52, b=20))
    return _fig(fig)


def grafico_recuperacion(r):
    prods = r['productos']
    fig = go.Figure(go.Bar(
        x=[f"{p['simbolo']} · {p['nombre']}" for p in prods],
        y=[p['recuperacion'] or 0 for p in prods],
        text=[f"{(p['recuperacion'] or 0):.2f} %" for p in prods],
        textposition='outside',
        marker=dict(color=['#0e7490' if p['es_concentrado'] else '#dc2626' for p in prods]),
        hovertemplate='%{x}<br>Distribución: %{y:.2f} %<extra></extra>',
    ))
    fig.update_layout(
        title=f'Distribución del metal por producto (base: ley {r["etiqueta_base"]})',
        xaxis=dict(title='Producto'),
        yaxis=dict(title='% del metal alimentado', range=[0, 105]),
        showlegend=False,
    )
    return _fig(fig)


def grafico_leyes(r):
    """Leyes de los productos junto a las dos leyes de cabeza."""
    u = r['unidad']
    etiquetas, valores, colores = [], [], []

    if r['f_ensayada']:
        etiquetas.append('f ens.')
        valores.append(r['f_ensayada'])
        colores.append('#94a3b8')
    etiquetas.append('f calc.')
    valores.append(r['f_calculada'])
    colores.append('#0e7490')

    for p in r['productos']:
        etiquetas.append(p['simbolo'])
        valores.append(p['ley'])
        colores.append('#059669' if p['es_concentrado'] else '#dc2626')

    fig = go.Figure(go.Bar(
        x=etiquetas, y=valores, marker=dict(color=colores),
        text=[f'{v:,.4g}' for v in valores], textposition='outside',
        hovertemplate=f'%{{x}}<br>Ley: %{{y:.4g}} {u}<extra></extra>',
    ))
    fig.update_layout(
        title=f'Leyes de cabeza y de productos ({u})',
        xaxis=dict(title='Corriente'),
        # Holgura superior para que no se corten las etiquetas de valor
        yaxis=dict(title=f'Ley ({u})', range=[0, max(valores) * 1.18]),
        showlegend=False,
    )
    return _fig(fig)


def grafico_cabeza(r):
    """Comparación de la ley de cabeza ensayada frente a la calculada."""
    if not (r['f_ensayada'] and r['cabeza_independiente']):
        return None

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=['Ensayada<br>(muestreo de cabeza)', 'Calculada<br>(reconstituida)'],
        y=[r['f_ensayada'], r['f_calculada']],
        marker=dict(color=['#94a3b8', '#0e7490']),
        text=[f'{r["f_ensayada"]:,.4g}', f'{r["f_calculada"]:,.4g}'],
        textposition='outside',
        hovertemplate=f'%{{x}}<br>%{{y:.4g}} {r["unidad"]}<extra></extra>',
    ))
    # Banda de tolerancia de ±5 % alrededor de la ley ensayada
    fig.add_hrect(y0=r['f_ensayada'] * (1 - TOLERANCIA_CABEZA_PCT / 100),
                  y1=r['f_ensayada'] * (1 + TOLERANCIA_CABEZA_PCT / 100),
                  fillcolor='rgba(5,150,105,.14)', line_width=0,
                  annotation_text=f'tolerancia ±{TOLERANCIA_CABEZA_PCT:g} %',
                  annotation_position='bottom right',
                  annotation_font_size=10)
    # Holgura superior para que no se corten las etiquetas de valor
    techo = max(r['f_ensayada'], r['f_calculada']) * 1.28
    fig.update_layout(
        title='Ley de cabeza: ensayada frente a calculada',
        yaxis=dict(title=f'Ley ({r["unidad"]})', range=[0, techo]),
        xaxis=dict(title=''), showlegend=False,
        bargap=0.45,
    )
    return _fig(fig)


def grafico_ley_recuperacion(r):
    """Curva ley-recuperación: el compromiso central de toda concentración.

    Solo tiene sentido con un concentrado: se hace variar la ley del
    concentrado manteniendo f y t, aplicando la fórmula de dos productos.
    """
    if r['n_concentrados'] != 1:
        return None
    f, t = r['f_usada'], r['t']
    c_actual = r['productos'][0]['ley']
    if c_actual <= f or f <= t:
        return None

    leyes = np.linspace(f * 1.05, c_actual * 1.6, 80)
    rec = [c * (f - t) / (f * (c - t)) * 100 for c in leyes]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=leyes, y=rec, mode='lines', name='Curva teórica',
        line=dict(width=3),
        hovertemplate=f'Ley concentrado: %{{x:.3g}} {r["unidad"]}<br>Recuperación: %{{y:.2f}} %<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=[c_actual], y=[r['recuperacion_total']], mode='markers+text',
        name='Operación actual', marker=dict(size=15, symbol='diamond'),
        text=['Actual'], textposition='top center',
        hovertemplate=f'Actual<br>Ley: %{{x:.3g}} {r["unidad"]}<br>Recuperación: %{{y:.2f}} %<extra></extra>',
    ))
    fig.update_layout(
        title=f'Curva ley-recuperación (ley de cabeza {r["etiqueta_base"]} y t constantes)',
        xaxis=dict(title=f'Ley del concentrado c ({r["unidad"]})'),
        yaxis=dict(title='Recuperación (%)', range=[0, 105]),
        hovermode='x unified',
    )
    return _fig(fig)


def interpretar(r):
    notas = []
    u = r['unidad']

    # ---- Ley de cabeza ----
    if r['f_ensayada'] and r['cabeza_independiente']:
        signo = 'superior' if r['dif_cabeza_abs'] > 0 else 'inferior'
        if r['cabeza_ok']:
            notas.append({'color': 'success', 'texto': (
                f'La ley de cabeza calculada ({r["f_calculada"]:,.4g} {u}) es un {abs(r["dif_cabeza_rel"]):,.2f} % '
                f'{signo} a la ensayada ({r["f_ensayada"]:,.4g} {u}). La diferencia está dentro de la '
                f'tolerancia habitual de ±{TOLERANCIA_CABEZA_PCT:g} %, lo que respalda la calidad del '
                'muestreo y de los análisis.')})
        else:
            notas.append({'color': 'danger', 'texto': (
                f'La ley de cabeza calculada ({r["f_calculada"]:,.4g} {u}) difiere un '
                f'{abs(r["dif_cabeza_rel"]):,.2f} % de la ensayada ({r["f_ensayada"]:,.4g} {u}), por encima '
                f'de la tolerancia de ±{TOLERANCIA_CABEZA_PCT:g} %. Revisa el muestreo de cabeza, el pesaje '
                'de los productos y los análisis químicos antes de dar el balance por válido.')})

        if r['rec_ensayada'] is not None and r['rec_calculada'] is not None:
            notas.append({'color': 'info', 'texto': (
                f'La recuperación resulta {r["rec_calculada"]:,.2f} % sobre la ley de cabeza calculada y '
                f'{r["rec_ensayada"]:,.2f} % sobre la ensayada. Se informa la primera porque hace cerrar '
                'el balance de metal y no puede superar el 100 %; la segunda sirve para dimensionar el '
                'error de muestreo.')})
    elif r['f_ensayada'] and not r['cabeza_independiente']:
        notas.append({'color': 'info', 'texto': (
            'La ley de cabeza calculada coincide con la ensayada porque los datos que faltaban se '
            'dedujeron precisamente del balance de metal. Para contrastar ambas leyes necesitas medir de '
            'forma independiente las masas y las leyes de todos los productos.')})
    else:
        notas.append({'color': 'info', 'texto': (
            f'Sin ensayo de cabeza, los resultados se calculan sobre la ley reconstituida de los '
            f'productos: f = {r["f_calculada"]:,.4g} {u}. Ingresa la ley de cabeza ensayada para '
            'verificar la consistencia del balance.')})

    # ---- Recuperación ----
    rec = r['recuperacion_total']
    if rec is not None:
        if rec > 100.5:
            color, txt = 'danger', ('La recuperación supera el 100 %, lo que es físicamente imposible. '
                                    'Ocurre al usar una ley de cabeza ensayada menor que la que indican '
                                    'los productos; cambia la base a la ley calculada o revisa los datos.')
        elif rec >= 90:
            color, txt = 'success', 'Recuperación alta: la operación captura la mayor parte del metal alimentado.'
        elif rec >= 75:
            color, txt = 'info', 'Recuperación en el rango habitual de una planta de concentración.'
        else:
            color, txt = 'warning', ('Recuperación baja: una fracción importante del metal se está perdiendo '
                                     'en el relave. Revisa la molienda, la dosificación de reactivos o el '
                                     'tiempo de flotación.')
        notas.append({'color': color, 'texto': (
            f'Recuperación global de {rec:,.2f} % sobre la ley de cabeza {r["etiqueta_base"]}. {txt}')})

    if r['ratio_concentracion']:
        notas.append({'color': 'info', 'texto': (
            f'Razón de concentración K = {r["ratio_concentracion"]:,.2f}: se necesitan '
            f'{r["ratio_concentracion"]:,.2f} toneladas de mineral para producir una tonelada de concentrado. '
            f'El concentrado representa el {r["rendimiento_masa"]:,.2f} % de la masa alimentada.')})

    if r['enriquecimiento_global']:
        notas.append({'color': 'info', 'texto': (
            f'Razón de enriquecimiento = {r["enriquecimiento_global"]:,.2f}: la ley del concentrado es '
            f'{r["enriquecimiento_global"]:,.2f} veces la ley de cabeza {r["etiqueta_base"]}.')})

    if not r['balance_masa_ok']:
        notas.append({'color': 'danger', 'texto': (
            f'El balance de masa no cierra: diferencia de {abs(r["error_masa"]):,.3f} unidades entre F y ΣC + T.')})

    return notas


# --------------------------------------------------------------- vista

@bp_balance_metalurgico.route('/', methods=['GET', 'POST'])
def balance_metalurgico():
    formulario = FormularioBalanceMetalurgico()
    contexto = {
        'formulario': formulario,
        'unidades': UNIDADES_LEY,
        'resultados': None,
        'graficos': {},
        'notas': [],
        'error_mensaje': None,
        'n_concentrados': N_CONCENTRADOS.get(formulario.tipo_balance.data or '1_concentrado', 1),
    }

    if request.method == 'POST':
        contexto['n_concentrados'] = N_CONCENTRADOS.get(formulario.tipo_balance.data or '1_concentrado', 1)
        resultados, error = calcular(formulario)
        if error:
            contexto['error_mensaje'] = error
        else:
            contexto['resultados'] = resultados
            contexto['notas'] = interpretar(resultados)
            contexto['graficos'] = {
                'cabeza': grafico_cabeza(resultados),
                'sankey': grafico_sankey_metal(resultados),
                'recuperacion': grafico_recuperacion(resultados),
                'leyes': grafico_leyes(resultados),
                'ley_recuperacion': grafico_ley_recuperacion(resultados),
            }

    return render_template('balance_metalurgico/balance.html', **contexto)
