"""Módulo V — Valorización de concentrados.

Reproduce la estructura de una liquidación comercial:

    Valor bruto del metal pagable
      − maquila (TC, treatment charge)
      − refinación (RC, refining charge)
      − penalidades por impurezas
      − flete y otros gastos de comercialización
    = NSR (Net Smelter Return)

El metal pagable se calcula con la regla habitual de contratos: se paga el
porcentaje acordado del contenido, sujeto a una deducción mínima en unidades
(metal base) o en gramos por tonelada (metales preciosos), aplicándose siempre
la deducción más desfavorable para el vendedor.
"""

import json

import numpy as np
import plotly.graph_objs as go
import plotly.utils
from flask import Blueprint, render_template, request

bp_valorizacion = Blueprint('valorizacion', __name__)

OZ_TROY_G = 31.1035          # gramos por onza troy
LB_POR_T = 2204.62           # libras por tonelada métrica

# Valores de referencia por metal base (deducciones y cargos habituales)
METALES = {
    'Cu': {'nombre': 'Cobre', 'ley': 28.0, 'pagable': 96.5, 'deduccion': 1.0,
           'precio': 8500.0, 'rc': 0.085, 'tc': 80.0},
    'Pb': {'nombre': 'Plomo', 'ley': 60.0, 'pagable': 95.0, 'deduccion': 3.0,
           'precio': 2100.0, 'rc': 0.0, 'tc': 130.0},
    'Zn': {'nombre': 'Zinc', 'ley': 52.0, 'pagable': 85.0, 'deduccion': 8.0,
           'precio': 2800.0, 'rc': 0.0, 'tc': 220.0},
}


def _num(nombre, defecto=0.0, minimo=None, maximo=None, etiqueta=None):
    crudo = str(request.form.get(nombre, '')).strip().replace(',', '.')
    visible = etiqueta or nombre
    if crudo == '':
        return defecto, None
    try:
        v = float(crudo)
    except ValueError:
        return None, f'«{visible}» debe ser un número.'
    if minimo is not None and v < minimo:
        return None, f'«{visible}» debe ser mayor o igual que {minimo:g}.'
    if maximo is not None and v > maximo:
        return None, f'«{visible}» debe ser menor o igual que {maximo:g}.'
    return v, None


def _fig(fig):
    return json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))


def _pagable_base(ley, pagable_pct, deduccion_unidades):
    """Ley pagable de un metal base: la deducción más desfavorable de las dos reglas."""
    por_porcentaje = ley * pagable_pct / 100
    por_deduccion = ley - deduccion_unidades
    return max(0.0, min(por_porcentaje, por_deduccion))


def _pagable_precioso(ley_gpt, pagable_pct, deduccion_gpt):
    """Ley pagable de un metal precioso, en g/t."""
    por_porcentaje = ley_gpt * pagable_pct / 100
    por_deduccion = ley_gpt - deduccion_gpt
    return max(0.0, min(por_porcentaje, por_deduccion))


def calcular(datos):
    """Construye la liquidación completa. Devuelve (resultados, error)."""
    q_humedo = datos['tonelaje']
    humedad = datos['humedad']
    q_seco = q_humedo * (1 - humedad / 100)

    if q_seco <= 0:
        return None, 'El tonelaje seco resultante es cero. Revisa el tonelaje húmedo y la humedad.'

    simbolo = datos['metal']
    meta = METALES.get(simbolo, METALES['Cu'])

    lineas = []          # cada línea pagable del concentrado
    deducciones = []     # cargos que se restan

    # ---- Metal base ----
    ley_base = datos['ley_base']
    if ley_base > 0:
        ley_pagable = _pagable_base(ley_base, datos['pagable_base'], datos['deduccion_base'])
        t_pagables = q_seco * ley_pagable / 100
        valor = t_pagables * datos['precio_base']
        lineas.append({
            'metal': meta['nombre'], 'simbolo': simbolo,
            'ley': ley_base, 'unidad_ley': '%',
            'ley_pagable': ley_pagable,
            'contenido': q_seco * ley_base / 100, 'unidad_contenido': 't',
            'pagable': t_pagables,
            'precio': datos['precio_base'], 'unidad_precio': 'USD/t',
            'valor': valor,
            'recuperacion_pct': ley_pagable / ley_base * 100 if ley_base else 0,
        })
        if datos['rc_base'] > 0:
            monto = t_pagables * LB_POR_T * datos['rc_base']
            deducciones.append({'concepto': f'Refinación de {meta["nombre"]} (RC)',
                                'detalle': f'{t_pagables * LB_POR_T:,.0f} lb × {datos["rc_base"]:,.4f} USD/lb',
                                'monto': monto})

    # ---- Metales preciosos ----
    for clave, nombre, simb in (('au', 'Oro', 'Au'), ('ag', 'Plata', 'Ag')):
        ley = datos[f'ley_{clave}']
        if ley <= 0:
            continue
        ley_pagable = _pagable_precioso(ley, datos[f'pagable_{clave}'], datos[f'deduccion_{clave}'])
        onzas = q_seco * ley_pagable / OZ_TROY_G
        valor = onzas * datos[f'precio_{clave}']
        lineas.append({
            'metal': nombre, 'simbolo': simb,
            'ley': ley, 'unidad_ley': 'g/t',
            'ley_pagable': ley_pagable,
            'contenido': q_seco * ley / OZ_TROY_G, 'unidad_contenido': 'oz',
            'pagable': onzas,
            'precio': datos[f'precio_{clave}'], 'unidad_precio': 'USD/oz',
            'valor': valor,
            'recuperacion_pct': ley_pagable / ley * 100 if ley else 0,
        })
        if datos[f'rc_{clave}'] > 0:
            monto = onzas * datos[f'rc_{clave}']
            deducciones.append({'concepto': f'Refinación de {nombre} (RC)',
                                'detalle': f'{onzas:,.2f} oz × {datos[f"rc_{clave}"]:,.2f} USD/oz',
                                'monto': monto})

    if not lineas:
        return None, 'Ingresa al menos una ley mayor que cero (metal base, oro o plata).'

    valor_bruto = sum(l['valor'] for l in lineas)

    # ---- Cargos por tonelada seca ----
    for etiqueta, campo in (('Maquila (TC)', 'tc'), ('Penalidades por impurezas', 'penalidades'),
                            ('Flete y gastos de comercialización', 'flete')):
        tarifa = datos[campo]
        if tarifa > 0:
            deducciones.append({'concepto': etiqueta,
                                'detalle': f'{q_seco:,.2f} dmt × {tarifa:,.2f} USD/dmt',
                                'monto': q_seco * tarifa})

    total_deducciones = sum(d['monto'] for d in deducciones)
    nsr = valor_bruto - total_deducciones
    nsr_por_dmt = nsr / q_seco if q_seco else 0

    pasos = [
        f'Tonelaje seco: {q_humedo:,.2f} wmt × (1 − {humedad:g}/100) = {q_seco:,.2f} dmt',
    ]
    for l in lineas:
        if l['unidad_ley'] == '%':
            pasos.append(
                f'{l["metal"]}: ley pagable = mín({l["ley"]:g} × {datos["pagable_base"]:g}%, '
                f'{l["ley"]:g} − {datos["deduccion_base"]:g}) = {l["ley_pagable"]:,.3f} % → '
                f'{l["pagable"]:,.3f} t × {l["precio"]:,.2f} USD/t = ${l["valor"]:,.2f}')
        else:
            pasos.append(
                f'{l["metal"]}: {l["ley_pagable"]:,.3f} g/t pagables × {q_seco:,.2f} dmt / '
                f'{OZ_TROY_G} g/oz = {l["pagable"]:,.2f} oz × {l["precio"]:,.2f} USD/oz = ${l["valor"]:,.2f}')
    pasos.append(f'Valor bruto del concentrado: ${valor_bruto:,.2f}')
    pasos.append(f'Total de deducciones: ${total_deducciones:,.2f}')
    pasos.append(f'NSR = {valor_bruto:,.2f} − {total_deducciones:,.2f} = ${nsr:,.2f} '
                 f'({nsr_por_dmt:,.2f} USD/dmt)')

    return {
        'q_humedo': q_humedo, 'humedad': humedad, 'q_seco': q_seco,
        'metal': simbolo, 'metal_nombre': meta['nombre'],
        'lineas': lineas, 'deducciones': deducciones,
        'valor_bruto': valor_bruto,
        'total_deducciones': total_deducciones,
        'nsr': nsr, 'nsr_por_dmt': nsr_por_dmt,
        'valor_bruto_por_dmt': valor_bruto / q_seco if q_seco else 0,
        'participacion_deducciones': (total_deducciones / valor_bruto * 100) if valor_bruto else 0,
        'datos': datos,
        'pasos': pasos,
    }, None


# --------------------------------------------------------------- gráficos

def grafico_cascada(r):
    """Cascada del valor bruto al NSR."""
    etiquetas, valores, medidas = [], [], []

    for l in r['lineas']:
        etiquetas.append(f'{l["simbolo"]} pagable')
        valores.append(l['valor'])
        medidas.append('relative')

    for d in r['deducciones']:
        etiquetas.append(d['concepto'].replace(' (RC)', ' RC').replace('Flete y gastos de comercialización', 'Flete'))
        valores.append(-d['monto'])
        medidas.append('relative')

    etiquetas.append('NSR')
    valores.append(0)
    medidas.append('total')

    fig = go.Figure(go.Waterfall(
        orientation='v', measure=medidas, x=etiquetas, y=valores,
        text=[f'${abs(v):,.0f}' if m != 'total' else f'${r["nsr"]:,.0f}' for v, m in zip(valores, medidas)],
        textposition='outside',
        connector={'line': {'width': 1, 'dash': 'dot'}},
        increasing={'marker': {'color': '#059669'}},
        decreasing={'marker': {'color': '#dc2626'}},
        totals={'marker': {'color': '#0e7490'}},
        hovertemplate='%{x}<br>%{y:$,.2f}<extra></extra>',
    ))
    fig.update_layout(
        title='Del valor bruto al retorno neto (NSR)',
        xaxis=dict(title=''), yaxis=dict(title='USD', tickformat='$,.0f'),
        showlegend=False, margin=dict(t=60, b=90),
    )
    return _fig(fig)


def grafico_aporte(r):
    """Aporte de cada metal al valor bruto."""
    if len(r['lineas']) < 2:
        return None
    fig = go.Figure(go.Pie(
        labels=[f'{l["metal"]} ({l["simbolo"]})' for l in r['lineas']],
        values=[l['valor'] for l in r['lineas']],
        hole=0.55, textinfo='label+percent',
        hovertemplate='%{label}<br>%{value:$,.2f}<br>%{percent}<extra></extra>',
    ))
    fig.update_layout(
        title='Aporte de cada metal al valor bruto',
        annotations=[dict(text=f'${r["valor_bruto"]:,.0f}', x=0.5, y=0.5,
                          font=dict(size=15), showarrow=False)],
        margin=dict(t=60, b=40),
    )
    return _fig(fig)


def grafico_sensibilidad_precio(r):
    """NSR frente a variaciones del precio del metal principal."""
    principal = r['lineas'][0]
    if principal['pagable'] <= 0:
        return None

    factores = np.linspace(0.6, 1.4, 60)
    precios = principal['precio'] * factores
    otros = sum(l['valor'] for l in r['lineas'][1:])
    nsr = principal['pagable'] * precios + otros - r['total_deducciones']

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=precios, y=nsr, mode='lines', line=dict(width=3), name='NSR',
        hovertemplate='Precio: %{x:$,.2f}<br>NSR: %{y:$,.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=[principal['precio']], y=[r['nsr']], mode='markers+text',
        name='Escenario actual', marker=dict(size=14, symbol='diamond'),
        text=['Actual'], textposition='top center',
    ))
    fig.add_hline(y=0, line_dash='dash', line_width=1.5,
                  annotation_text='punto de equilibrio', annotation_position='right')
    fig.update_layout(
        title=f'Sensibilidad del NSR al precio del {principal["metal"].lower()}',
        xaxis=dict(title=f'Precio ({principal["unidad_precio"]})', tickformat='$,.0f'),
        yaxis=dict(title='NSR (USD)', tickformat='$,.0f'),
        hovermode='x unified',
    )
    return _fig(fig)


def interpretar(r):
    notas = []
    if r['nsr'] <= 0:
        notas.append({'color': 'danger', 'texto': (
            'El retorno neto es negativo: las deducciones superan al valor del metal pagable. '
            'Con estos términos comerciales el concentrado no sería vendible; revisa la ley, '
            'la maquila o las penalidades.')})
    else:
        notas.append({'color': 'success', 'texto': (
            f'El concentrado deja un retorno neto de ${r["nsr"]:,.2f}, equivalente a '
            f'${r["nsr_por_dmt"]:,.2f} por tonelada seca. Las deducciones consumen el '
            f'{r["participacion_deducciones"]:,.1f} % del valor bruto.')})

    if r['participacion_deducciones'] > 45:
        notas.append({'color': 'warning', 'texto': (
            f'Las deducciones representan el {r["participacion_deducciones"]:,.1f} % del valor bruto, '
            'una proporción alta. Suele ocurrir con concentrados de baja ley o con penalidades '
            'elevadas por impurezas; conviene renegociar los términos o mejorar la calidad.')})

    principal = r['lineas'][0]
    if principal['unidad_ley'] == '%' and principal['recuperacion_pct'] < 90:
        notas.append({'color': 'info', 'texto': (
            f'Solo se paga el {principal["recuperacion_pct"]:,.1f} % del {principal["metal"].lower()} '
            f'contenido ({principal["ley_pagable"]:,.2f} % de los {principal["ley"]:,.2f} % de ley). '
            'A menor ley del concentrado, mayor peso relativo tiene la deducción de unidades.')})

    if len(r['lineas']) > 1:
        creditos = sum(l['valor'] for l in r['lineas'][1:])
        notas.append({'color': 'info', 'texto': (
            f'Los créditos por metales preciosos aportan ${creditos:,.2f}, es decir el '
            f'{creditos / r["valor_bruto"] * 100:,.1f} % del valor bruto.')})

    return notas


# --------------------------------------------------------------- vista

@bp_valorizacion.route('/', methods=['GET', 'POST'])
def valorizacion():
    contexto = {'metales': METALES, 'resultados': None, 'graficos': {},
                'notas': [], 'error_mensaje': None, 'entradas': request.form}

    if request.method != 'POST':
        return render_template('valorizacion/valorizacion.html', **contexto)

    simbolo = request.form.get('metal', 'Cu')
    if simbolo not in METALES:
        simbolo = 'Cu'
    ref = METALES[simbolo]

    campos = [
        ('tonelaje', 0.0, 0.0, None, 'Tonelaje húmedo'),
        ('humedad', 8.0, 0.0, 50.0, 'Humedad'),
        ('ley_base', 0.0, 0.0, 100.0, f'Ley de {ref["nombre"]}'),
        ('pagable_base', ref['pagable'], 0.0, 100.0, 'Porcentaje pagable del metal base'),
        ('deduccion_base', ref['deduccion'], 0.0, 50.0, 'Deducción de unidades'),
        ('precio_base', ref['precio'], 0.0, None, 'Precio del metal base'),
        ('rc_base', ref['rc'], 0.0, None, 'Cargo de refinación del metal base'),
        ('ley_au', 0.0, 0.0, 5000.0, 'Ley de oro'),
        ('pagable_au', 90.0, 0.0, 100.0, 'Porcentaje pagable de oro'),
        ('deduccion_au', 1.0, 0.0, 100.0, 'Deducción de oro'),
        ('precio_au', 2300.0, 0.0, None, 'Precio del oro'),
        ('rc_au', 6.0, 0.0, None, 'Cargo de refinación del oro'),
        ('ley_ag', 0.0, 0.0, 50000.0, 'Ley de plata'),
        ('pagable_ag', 90.0, 0.0, 100.0, 'Porcentaje pagable de plata'),
        ('deduccion_ag', 30.0, 0.0, 1000.0, 'Deducción de plata'),
        ('precio_ag', 28.0, 0.0, None, 'Precio de la plata'),
        ('rc_ag', 0.5, 0.0, None, 'Cargo de refinación de la plata'),
        ('tc', ref['tc'], 0.0, None, 'Maquila TC'),
        ('penalidades', 0.0, 0.0, None, 'Penalidades'),
        ('flete', 0.0, 0.0, None, 'Flete y gastos'),
    ]

    datos = {'metal': simbolo}
    for nombre, defecto, mn, mx, etiqueta in campos:
        v, err = _num(nombre, defecto, mn, mx, etiqueta)
        if err:
            contexto['error_mensaje'] = err
            return render_template('valorizacion/valorizacion.html', **contexto)
        datos[nombre] = v

    if datos['tonelaje'] <= 0:
        contexto['error_mensaje'] = 'Ingresa el tonelaje húmedo del lote de concentrado.'
        return render_template('valorizacion/valorizacion.html', **contexto)

    resultados, error = calcular(datos)
    if error:
        contexto['error_mensaje'] = error
    else:
        contexto['resultados'] = resultados
        contexto['notas'] = interpretar(resultados)
        contexto['graficos'] = {
            'cascada': grafico_cascada(resultados),
            'aporte': grafico_aporte(resultados),
            'sensibilidad': grafico_sensibilidad_precio(resultados),
        }

    return render_template('valorizacion/valorizacion.html', **contexto)
