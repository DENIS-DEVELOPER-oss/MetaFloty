"""Módulo IV — Dimensionamiento de equipos.

Modelos empleados (todos con unidades explícitas):

  · Molinos      Bond (1961) para el consumo específico y ecuación de potencia
                 de Bond-Rowland para despejar el diámetro del molino.
  · Hidrociclones Correlación de Plitt (1976) para el d50 corregido, con las
                 proporciones geométricas estándar de Krebs. La caída de presión
                 no se estima: debe tomarse de las curvas del fabricante.
  · Separadores  Criterio de concentración de Taggart y velocidad terminal
                 (Stokes o Newton según el régimen de Reynolds).
  · Silos        Geometría cilindro + tolva cónica y presión de pared de Janssen.

Los resultados son estimaciones de ingeniería conceptual: sirven para
prediseño y comparación de alternativas, no reemplazan el diseño de detalle
del fabricante.
"""

import json
import math

import numpy as np
import plotly.graph_objs as go
import plotly.utils
from flask import Blueprint, render_template, request

bp_dimensionamiento = Blueprint('dimensionamiento', __name__)

G = 9.81          # m/s²
MU_AGUA = 0.001   # Pa·s a 20 °C


# --------------------------------------------------------------- utilidades

def _num(nombre, defecto=None, minimo=None, maximo=None, etiqueta=None):
    """Lee un número del formulario. Devuelve (valor, error)."""
    crudo = request.form.get(nombre, '')
    texto = str(crudo).strip().replace(',', '.')
    nombre_visible = etiqueta or nombre

    if texto == '':
        if defecto is None:
            return None, f'Falta el dato «{nombre_visible}».'
        return defecto, None
    try:
        v = float(texto)
    except ValueError:
        return None, f'«{nombre_visible}» debe ser un número.'
    if minimo is not None and v < minimo:
        return None, f'«{nombre_visible}» debe ser mayor o igual que {minimo:g}.'
    if maximo is not None and v > maximo:
        return None, f'«{nombre_visible}» debe ser menor o igual que {maximo:g}.'
    return v, None


def _fig(fig):
    return json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))


def _vista(plantilla, **extra):
    base = {'resultados': None, 'graficos': {}, 'notas': [], 'error_mensaje': None, 'entradas': request.form}
    base.update(extra)
    return render_template(plantilla, **base)


# =============================================================== MOLINOS

def _factor_velocidad(nc):
    """Término de la ecuación de potencia de Bond que depende de la velocidad."""
    exponente = 9 - 10 * nc
    # Se acota el exponente para evitar desbordes numéricos con Nc extremos
    exponente = max(-30.0, min(30.0, exponente))
    return 1 - 0.1 / (2 ** exponente)


def potencia_bond_molino(D, L, rho_carga, J, nc):
    """Potencia al eje que demanda un molino tumbling, en kW.

    P = 12,262 · D^2,3 · L · ρb · J · (1 − 0,937·J) · [1 − 0,1/2^(9−10Nc)] · Nc
    D y L en metros, ρb en t/m³.
    """
    return (12.262 * (D ** 2.3) * L * rho_carga * J *
            (1 - 0.937 * J) * _factor_velocidad(nc) * nc)


def dimensionar_molino(tipo, F, Wi, P80, F80, rho_carga, L_D, J, nc, eficiencia):
    """Calcula potencia de Bond y despeja la geometría del molino."""
    if P80 >= F80:
        return None, ('El P80 del producto debe ser menor que el F80 de la alimentación: '
                      'un molino reduce el tamaño, no lo aumenta.')

    # 1 · Consumo específico de energía (kWh/t)
    w = 10 * Wi * (1 / math.sqrt(P80) - 1 / math.sqrt(F80))
    # 2 · Potencia al eje (kW) y potencia instalada del motor
    potencia_eje = w * F
    potencia_motor = potencia_eje / eficiencia

    # 3 · Geometría: P ∝ D^2,3 · L = D^3,3 · (L/D)  →  se despeja D
    k = 12.262 * L_D * rho_carga * J * (1 - 0.937 * J) * _factor_velocidad(nc) * nc
    if k <= 0:
        return None, 'Los parámetros de carga y velocidad no producen una potencia positiva. Revísalos.'
    D = (potencia_eje / k) ** (1 / 3.3)
    L = L_D * D

    # 4 · Verificación y magnitudes derivadas
    potencia_verif = potencia_bond_molino(D, L, rho_carga, J, nc)
    volumen = math.pi / 4 * D ** 2 * L
    volumen_carga = volumen * J
    masa_carga = volumen_carga * rho_carga            # t
    vel_critica = 42.3 / math.sqrt(D) if D > 0 else 0  # rpm
    vel_operacion = vel_critica * nc
    razon_reduccion = F80 / P80

    # Tamaño de bola/barra de reposición (Bond)
    if tipo == 'bolas':
        b_mm = 25.4 * ((F80 / 1000) ** 0.5 * (rho_carga * Wi / (100 * nc * (3.281 * D) ** 0.5)) ** (1 / 3))
        etiqueta_cuerpo = 'Diámetro de bola de reposición'
    else:
        b_mm = 25.4 * ((F80 / 1000) ** 0.75 * (rho_carga * Wi / (100 * nc * (3.281 * D) ** 0.5)) ** 0.5)
        etiqueta_cuerpo = 'Diámetro de barra de reposición'

    return {
        'tipo': tipo,
        'capacidad': F, 'work_index': Wi, 'p80': P80, 'f80': F80,
        'rho_carga': rho_carga, 'L_D': L_D, 'J': J, 'nc': nc, 'eficiencia': eficiencia,
        'consumo_especifico': w,
        'potencia_eje': potencia_eje,
        'potencia_motor': potencia_motor,
        'potencia_verificacion': potencia_verif,
        'diametro': D, 'longitud': L,
        'volumen': volumen, 'volumen_carga': volumen_carga, 'masa_carga': masa_carga,
        'vel_critica': vel_critica, 'vel_operacion': vel_operacion,
        'razon_reduccion': razon_reduccion,
        'cuerpo_moledor': b_mm, 'etiqueta_cuerpo': etiqueta_cuerpo,
        'energia_dia': potencia_eje * 24,
        'pasos': [
            f'Consumo específico (Bond): W = 10 × {Wi:g} × (1/√{P80:g} − 1/√{F80:g}) = {w:,.3f} kWh/t',
            f'Potencia al eje: P = W × F = {w:,.3f} × {F:g} = {potencia_eje:,.1f} kW',
            f'Potencia instalada (η = {eficiencia:.0%}): {potencia_motor:,.1f} kW',
            'Ecuación de potencia: P = 12,262·D^2,3·L·ρb·J·(1−0,937J)·[1−0,1/2^(9−10Nc)]·Nc',
            f'Con L = {L_D:g}·D se despeja D = {D:,.2f} m y L = {L:,.2f} m',
            f'Verificación: la geometría obtenida demanda {potencia_verif:,.1f} kW',
            f'Velocidad crítica: Nc = 42,3/√D = {vel_critica:,.2f} rpm → operación a {vel_operacion:,.2f} rpm',
        ],
    }, None


def grafico_sensibilidad_molino(r):
    """Cómo cambia la potencia requerida al variar el P80 objetivo."""
    p80_min = max(r['p80'] * 0.4, 10)
    p80_max = min(r['p80'] * 3, r['f80'] * 0.9)
    if p80_max <= p80_min:
        return None
    p80 = np.linspace(p80_min, p80_max, 60)
    w = 10 * r['work_index'] * (1 / np.sqrt(p80) - 1 / math.sqrt(r['f80']))
    potencia = w * r['capacidad']

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=p80, y=potencia, mode='lines', name='Potencia requerida', line=dict(width=3),
        hovertemplate='P80 = %{x:.0f} µm<br>Potencia = %{y:.1f} kW<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=[r['p80']], y=[r['potencia_eje']], mode='markers+text',
        name='Punto de diseño', marker=dict(size=14, symbol='diamond'),
        text=['Diseño'], textposition='top center',
    ))
    fig.update_layout(
        title='Sensibilidad de la potencia al P80 objetivo',
        xaxis=dict(title='P80 del producto (µm)'),
        yaxis=dict(title='Potencia al eje (kW)'),
        hovermode='x unified',
    )
    return _fig(fig)


def grafico_potencia_velocidad(r):
    """Potencia demandada según la fracción de velocidad crítica y el llenado."""
    nc = np.linspace(0.55, 0.85, 40)
    fig = go.Figure()
    for j in (0.25, 0.30, 0.35, 0.40):
        p = [potencia_bond_molino(r['diametro'], r['longitud'], r['rho_carga'], j, x) for x in nc]
        fig.add_trace(go.Scatter(
            x=nc * 100, y=p, mode='lines', name=f'J = {j:.0%}',
            line=dict(width=2.5 if abs(j - r['J']) < 0.001 else 1.8,
                      dash='solid' if abs(j - r['J']) < 0.001 else 'dot'),
            hovertemplate='Nc = %{x:.0f} %<br>P = %{y:.1f} kW<extra></extra>',
        ))
    fig.add_trace(go.Scatter(
        x=[r['nc'] * 100], y=[r['potencia_verificacion']], mode='markers',
        name='Punto de operación', marker=dict(size=14, symbol='diamond'),
    ))
    fig.update_layout(
        title='Potencia del molino según velocidad y llenado',
        xaxis=dict(title='Fracción de la velocidad crítica (%)'),
        yaxis=dict(title='Potencia al eje (kW)'),
        hovermode='x unified',
    )
    return _fig(fig)


def notas_molino(r):
    notas = []
    if r['razon_reduccion'] < 4:
        notas.append({'color': 'warning', 'texto': (
            f'La razón de reducción es {r["razon_reduccion"]:,.1f}, baja para un molino. '
            'Verifica si la etapa realmente requiere molienda o basta con clasificación.')})
    elif r['razon_reduccion'] > 100:
        notas.append({'color': 'warning', 'texto': (
            f'La razón de reducción es {r["razon_reduccion"]:,.0f}, muy alta para una sola etapa. '
            'Normalmente se resuelve con dos etapas de conminución en serie.')})

    if not (0.60 <= r['nc'] <= 0.82):
        notas.append({'color': 'warning', 'texto': (
            f'La velocidad de operación ({r["nc"]:.0%} de la crítica) queda fuera del rango industrial '
            'habitual de 65 % a 80 %.')})

    lim = (1.2, 2.4) if r['tipo'] == 'barras' else (0.9, 1.8)
    if not (lim[0] <= r['L_D'] <= lim[1]):
        notas.append({'color': 'info', 'texto': (
            f'La relación L/D = {r["L_D"]:g} está fuera del rango típico '
            f'({lim[0]:g}–{lim[1]:g}) para molinos de {r["tipo"]}.')})

    notas.append({'color': 'info', 'texto': (
        f'El molino contendría {r["masa_carga"]:,.1f} t de carga moledora ocupando '
        f'{r["volumen_carga"]:,.1f} m³ de los {r["volumen"]:,.1f} m³ del cuerpo. '
        f'{r["etiqueta_cuerpo"]} estimado: {r["cuerpo_moledor"]:,.1f} mm.')})
    return notas


def _molino(tipo, plantilla, L_D_def):
    if request.method != 'POST':
        return _vista(plantilla, tipo=tipo)

    campos = [
        ('capacidad_tratamiento', None, 0.01, None, 'Capacidad de tratamiento F'),
        ('indice_trabajo', None, 0.1, 100, 'Índice de trabajo Wi'),
        ('p80_producto', None, 1, None, 'P80 del producto'),
        ('f80_alimentacion', None, 1, None, 'F80 de la alimentación'),
        ('densidad_carga', None, 0.5, 12, 'Densidad aparente de la carga'),
        ('relacion_largo_diametro', L_D_def, 0.3, 4, 'Relación L/D'),
        ('llenado', 0.35 if tipo == 'bolas' else 0.40, 0.05, 0.55, 'Fracción de llenado J'),
        ('velocidad_critica', 0.72, 0.3, 0.95, 'Fracción de velocidad crítica Nc'),
        ('eficiencia', 0.92, 0.5, 1.0, 'Eficiencia motor-transmisión'),
    ]
    valores = {}
    for nombre, defecto, mn, mx, etiqueta in campos:
        v, err = _num(nombre, defecto, mn, mx, etiqueta)
        if err:
            return _vista(plantilla, tipo=tipo, error_mensaje=err)
        valores[nombre] = v

    resultados, error = dimensionar_molino(
        tipo,
        valores['capacidad_tratamiento'], valores['indice_trabajo'],
        valores['p80_producto'], valores['f80_alimentacion'],
        valores['densidad_carga'], valores['relacion_largo_diametro'],
        valores['llenado'], valores['velocidad_critica'], valores['eficiencia'])

    if error:
        return _vista(plantilla, tipo=tipo, error_mensaje=error)

    return _vista(plantilla, tipo=tipo, resultados=resultados, notas=notas_molino(resultados),
                  graficos={'sensibilidad': grafico_sensibilidad_molino(resultados),
                            'potencia': grafico_potencia_velocidad(resultados)})


@bp_dimensionamiento.route('/molino-barras', methods=['GET', 'POST'])
def molino_barras():
    return _molino('barras', 'dimensionamiento/molino_barras.html', 1.6)


@bp_dimensionamiento.route('/molino-bolas', methods=['GET', 'POST'])
def molino_bolas():
    return _molino('bolas', 'dimensionamiento/molino_bolas.html', 1.3)


# =============================================================== HIDROCICLONES

# Proporciones geométricas estándar (Krebs), como fracción del diámetro Dc
PROP_CICLON = {'Di': 0.15, 'Do': 0.25, 'Du': 0.15, 'h': 4.0}


def _plitt_d50c(Dc_cm, Q_m3h, cv_pct, delta_rho_gcm3):
    """d50 corregido según Plitt (1976), en µm. Longitudes en cm, Q en m³/h."""
    Di = PROP_CICLON['Di'] * Dc_cm
    Do = PROP_CICLON['Do'] * Dc_cm
    Du = PROP_CICLON['Du'] * Dc_cm
    h = PROP_CICLON['h'] * Dc_cm
    return (50.5 * (Dc_cm ** 0.46) * (Di ** 0.6) * (Do ** 1.21) * math.exp(0.063 * cv_pct)) / \
           ((Du ** 0.71) * (h ** 0.38) * (Q_m3h ** 0.45) * (delta_rho_gcm3 ** 0.5))


def _resolver_dc(d50_objetivo, Q_unit, cv, delta_rho):
    """Diámetro de ciclón que produce el corte pedido (bisección)."""
    lo, hi = 2.0, 200.0        # cm
    f_lo = _plitt_d50c(lo, Q_unit, cv, delta_rho) - d50_objetivo
    f_hi = _plitt_d50c(hi, Q_unit, cv, delta_rho) - d50_objetivo
    if f_lo * f_hi > 0:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        f_mid = _plitt_d50c(mid, Q_unit, cv, delta_rho) - d50_objetivo
        if abs(f_mid) < 1e-9:
            break
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


@bp_dimensionamiento.route('/hidrociclones', methods=['GET', 'POST'])
def hidrociclones():
    plantilla = 'dimensionamiento/hidrociclones.html'
    if request.method != 'POST':
        return _vista(plantilla)

    campos = [
        ('caudal', None, 0.1, None, 'Caudal de pulpa Q'),
        ('tamano_corte', None, 1, 2000, 'Tamaño de corte d50c'),
        ('densidad_solido', None, 1.0, 12, 'Densidad del sólido'),
        ('densidad_liquido', 1.0, 0.5, 3, 'Densidad del líquido'),
        ('concentracion_volumen', 20.0, 0.1, 55, 'Concentración de sólidos en volumen'),
        ('caudal_unitario', 0.0, 0.0, None, 'Caudal por ciclón'),
    ]
    v = {}
    for nombre, defecto, mn, mx, etiqueta in campos:
        val, err = _num(nombre, defecto, mn, mx, etiqueta)
        if err:
            return _vista(plantilla, error_mensaje=err)
        v[nombre] = val

    delta_rho = v['densidad_solido'] - v['densidad_liquido']
    if delta_rho <= 0:
        return _vista(plantilla, error_mensaje=(
            'La densidad del sólido debe ser mayor que la del líquido; de lo contrario '
            'no hay fuerza impulsora para la clasificación.'))

    Q_total = v['caudal']
    Q_unit = v['caudal_unitario'] if v['caudal_unitario'] > 0 else Q_total
    if Q_unit > Q_total:
        Q_unit = Q_total

    Dc = _resolver_dc(v['tamano_corte'], Q_unit, v['concentracion_volumen'], delta_rho)
    if Dc is None:
        return _vista(plantilla, error_mensaje=(
            'No existe un diámetro de ciclón entre 2 cm y 200 cm que produzca ese corte con el '
            'caudal indicado. Prueba con un caudal por ciclón menor o con un corte menos exigente.'))

    n_ciclones = max(1, math.ceil(Q_total / Q_unit))

    geometria = {clave: PROP_CICLON[clave] * Dc for clave in PROP_CICLON}
    area_entrada = math.pi / 4 * (geometria['Di'] / 100) ** 2      # m²
    vel_entrada = (Q_unit / 3600) / area_entrada if area_entrada else 0
    cv_frac = v['concentracion_volumen'] / 100
    rho_pulpa = (v['densidad_liquido'] * (1 - cv_frac)
                 + v['densidad_solido'] * cv_frac) * 1000     # kg/m3

    # Velocidad terminal de una partícula del tamaño de corte (referencia)
    d_m = v['tamano_corte'] * 1e-6
    vt_stokes = G * d_m ** 2 * (delta_rho * 1000) / (18 * MU_AGUA)

    resultados = {
        'caudal_unitario': Q_unit, 'n_ciclones': n_ciclones,
        'd50c': v['tamano_corte'],
        'densidad_solido': v['densidad_solido'], 'densidad_liquido': v['densidad_liquido'],
        'delta_rho': delta_rho, 'cv': v['concentracion_volumen'],
        'diametro_cm': Dc, 'diametro_pulg': Dc / 2.54,
        'geometria': geometria,
        'velocidad_entrada': vel_entrada,
        'densidad_pulpa': rho_pulpa,
        'vt_stokes': vt_stokes,
        'pasos': [
            f'Se fija el caudal por ciclón en {Q_unit:,.1f} m³/h y las proporciones estándar '
            f'Di = 0,15·Dc, Do = 0,25·Dc, Du = 0,15·Dc, h = 4·Dc.',
            'Correlación de Plitt: d50c = 50,5·Dc^0,46·Di^0,6·Do^1,21·e^(0,063·Cv) / '
            '(Du^0,71·h^0,38·Q^0,45·Δρ^0,5)',
            f'Se resuelve numéricamente para d50c = {v["tamano_corte"]:g} µm → Dc = {Dc:,.2f} cm '
            f'({Dc / 2.54:,.1f} pulgadas)',
            f'Número de unidades: N = Q_total / Q_unitario = {Q_total:,.1f} / {Q_unit:,.1f} → '
            f'{n_ciclones} ciclón(es) en operación',
            f'Velocidad en la entrada tangencial: v = Q/A = {vel_entrada:,.2f} m/s '
            f'(densidad de pulpa {rho_pulpa:,.0f} kg/m³)',
        ],
    }

    notas = []
    if vel_entrada < 5:
        notas.append({'color': 'warning', 'texto': (
            f'La velocidad en la entrada tangencial es de {vel_entrada:,.1f} m/s, por debajo del '
            'rango habitual de 5 a 20 m/s. Con poca energía de entrada el campo centrífugo es débil '
            'y la clasificación pierde nitidez: usa un ciclón más pequeño o sube el caudal unitario.')})
    elif vel_entrada > 20:
        notas.append({'color': 'warning', 'texto': (
            f'La velocidad en la entrada tangencial es de {vel_entrada:,.1f} m/s, por encima del rango '
            'habitual de 5 a 20 m/s. Implica alta presión de bombeo y desgaste acelerado del ápex: '
            'reparte el caudal entre más unidades en paralelo.')})
    else:
        notas.append({'color': 'success', 'texto': (
            f'La velocidad en la entrada tangencial ({vel_entrada:,.1f} m/s) está dentro del rango '
            'de diseño habitual de 5 a 20 m/s.')})

    notas.append({'color': 'info', 'texto': (
        'La caída de presión no se estima en este módulo: depende demasiado de la geometría real '
        '(entrada rectangular, tipo de ápex, revestimiento) y debe tomarse de las curvas del '
        'fabricante. Como referencia, los hidrociclones industriales operan entre 70 y 140 kPa '
        '(10 a 20 psi).')})

    notas.append({'color': 'info', 'texto': (
        'Las proporciones geométricas son las de la familia estándar Krebs. Si el fabricante '
        'propone otras (por ejemplo un ápex distinto), el corte cambiará respecto a esta estimación.')})

    return _vista(plantilla, resultados=resultados, notas=notas, graficos={
        'corte': grafico_corte_ciclon(resultados),
        'geometria': grafico_geometria_ciclon(resultados),
    })


def grafico_corte_ciclon(r):
    """Cómo varía el corte con el diámetro del ciclón, al caudal de diseño."""
    dc = np.linspace(max(2, r['diametro_cm'] * 0.3), r['diametro_cm'] * 2.2, 70)
    d50 = [_plitt_d50c(x, r['caudal_unitario'], r['cv'], r['delta_rho']) for x in dc]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dc, y=d50, mode='lines', name='d50c según Plitt', line=dict(width=3),
        hovertemplate='Dc = %{x:.1f} cm<br>d50c = %{y:.1f} µm<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=[r['diametro_cm']], y=[r['d50c']], mode='markers+text',
        name='Diseño', marker=dict(size=14, symbol='diamond'),
        text=['Diseño'], textposition='top center',
    ))
    fig.update_layout(
        title=f'Tamaño de corte según el diámetro del ciclón (Q = {r["caudal_unitario"]:,.0f} m³/h)',
        xaxis=dict(title='Diámetro del ciclón Dc (cm)'),
        yaxis=dict(title='d50 corregido (µm)'),
        hovermode='x unified',
    )
    return _fig(fig)


def grafico_geometria_ciclon(r):
    g = r['geometria']
    etiquetas = ['Dc · cuerpo', 'Di · entrada', 'Do · vórtex', 'Du · ápex', 'h · altura']
    valores = [r['diametro_cm'], g['Di'], g['Do'], g['Du'], g['h']]
    fig = go.Figure(go.Bar(
        x=etiquetas, y=valores, text=[f'{v:,.1f} cm' for v in valores], textposition='outside',
        hovertemplate='%{x}<br>%{y:.2f} cm<extra></extra>',
    ))
    fig.update_layout(
        title='Dimensiones resultantes del ciclón',
        xaxis=dict(title=''), yaxis=dict(title='Dimensión (cm)'), showlegend=False,
    )
    return _fig(fig)


# =============================================================== SEPARADORES

@bp_dimensionamiento.route('/separadores', methods=['GET', 'POST'])
def separadores():
    plantilla = 'dimensionamiento/separadores.html'
    if request.method != 'POST':
        return _vista(plantilla)

    campos = [
        ('densidad_mineral', None, 1.0, 25, 'Densidad del mineral pesado'),
        ('densidad_ganga', None, 1.0, 25, 'Densidad de la ganga'),
        ('densidad_fluido', 1.0, 0.5, 3.0, 'Densidad del fluido'),
        ('tamano_particula', None, 0.001, 100, 'Tamaño de partícula'),
        ('viscosidad', 0.001, 1e-6, 1.0, 'Viscosidad del fluido'),
    ]
    v = {}
    for nombre, defecto, mn, mx, etiqueta in campos:
        val, err = _num(nombre, defecto, mn, mx, etiqueta)
        if err:
            return _vista(plantilla, error_mensaje=err)
        v[nombre] = val

    rho_h, rho_l, rho_f = v['densidad_mineral'], v['densidad_ganga'], v['densidad_fluido']
    if rho_h <= rho_f or rho_l <= rho_f:
        return _vista(plantilla, error_mensaje=(
            'Las densidades del mineral y de la ganga deben ser mayores que la del fluido.'))
    if rho_h <= rho_l:
        return _vista(plantilla, error_mensaje=(
            'La densidad del mineral pesado debe superar a la de la ganga; de lo contrario '
            'no hay contraste que permita la separación gravimétrica.'))

    cc = (rho_h - rho_f) / (rho_l - rho_f)

    if cc > 2.5:
        viabilidad = ('Separación fácil a cualquier tamaño', 'success', 'hasta ~75 µm')
    elif cc > 1.75:
        viabilidad = ('Separación posible con partículas finas', 'success', 'hasta ~150 µm')
    elif cc > 1.50:
        viabilidad = ('Separación posible con partículas medias', 'warning', 'hasta ~1,7 mm')
    elif cc > 1.25:
        viabilidad = ('Separación difícil, solo material grueso', 'warning', 'solo > 6 mm')
    else:
        viabilidad = ('Separación gravimétrica no viable', 'danger', 'no aplicable')

    # Velocidad terminal: Stokes y verificación del régimen
    d_m = v['tamano_particula'] / 1000.0            # mm → m
    mu = v['viscosidad']
    dr = (rho_h - rho_f) * 1000                     # kg/m³

    vt_stokes = G * d_m ** 2 * dr / (18 * mu)
    re_stokes = rho_f * 1000 * vt_stokes * d_m / mu
    vt_newton = 1.74 * math.sqrt(G * d_m * dr / (rho_f * 1000))
    re_newton = rho_f * 1000 * vt_newton * d_m / mu

    if re_stokes < 1:
        regimen, vt, re = 'Laminar (Stokes)', vt_stokes, re_stokes
        nota_reg = 'Re < 1: la ley de Stokes es válida.'
    elif re_newton > 1000:
        regimen, vt, re = 'Turbulento (Newton)', vt_newton, re_newton
        nota_reg = 'Re > 1000: se aplica la ley de Newton para régimen turbulento.'
    else:
        regimen = 'Transición (intermedio)'
        vt = min(vt_stokes, vt_newton)
        re = rho_f * 1000 * vt * d_m / mu
        nota_reg = ('1 < Re < 1000: régimen de transición, donde no aplica ninguna de las dos leyes '
                    'límite. Se adopta el menor valor entre Stokes y Newton como estimación '
                    'conservadora; para diseño usa una correlación específica de la zona intermedia.')

    # Velocidad terminal de la ganga, para estimar la selectividad
    dr_l = (rho_l - rho_f) * 1000
    vt_l_stokes = G * d_m ** 2 * dr_l / (18 * mu)
    vt_l_newton = 1.74 * math.sqrt(G * d_m * dr_l / (rho_f * 1000))
    vt_l = vt_l_stokes if re_stokes < 1 else (vt_l_newton if re_newton > 1000 else min(vt_l_stokes, vt_l_newton))
    razon_velocidades = vt / vt_l if vt_l else None

    resultados = {
        'rho_h': rho_h, 'rho_l': rho_l, 'rho_f': rho_f,
        'tamano': v['tamano_particula'], 'viscosidad': mu,
        'criterio': cc,
        'viabilidad': viabilidad[0], 'viabilidad_color': viabilidad[1], 'limite': viabilidad[2],
        'vt_mm_s': vt * 1000, 'reynolds': re, 'regimen': regimen, 'nota_regimen': nota_reg,
        'vt_stokes': vt_stokes, 'vt_newton': vt_newton,
        'vt_ganga': vt_l, 'razon_velocidades': razon_velocidades,
        'delta_densidad': rho_h - rho_l,
        'pasos': [
            f'Criterio de concentración: CC = (ρ_pesado − ρ_fluido)/(ρ_liviano − ρ_fluido) = '
            f'({rho_h:g} − {rho_f:g})/({rho_l:g} − {rho_f:g}) = {cc:,.3f}',
            f'Velocidad terminal de Stokes: v = g·d²·Δρ/(18·μ) = {vt_stokes:,.5f} m/s',
            f'Número de Reynolds asociado: Re = ρ_f·v·d/μ = {re_stokes:,.3f}',
            f'Régimen identificado: {regimen} → velocidad adoptada {vt:,.5f} m/s ({vt * 1000:,.2f} mm/s)',
            (f'Razón de velocidades pesado/liviano = {razon_velocidades:,.2f}' if razon_velocidades else ''),
        ],
    }

    notas = [
        {'color': viabilidad[1], 'texto': (
            f'Criterio de concentración CC = {cc:,.2f}: {viabilidad[0].lower()}. '
            f'Tamaño mínimo tratable de referencia: {viabilidad[2]}.')},
        {'color': 'info', 'texto': nota_reg},
    ]
    if razon_velocidades:
        notas.append({'color': 'info', 'texto': (
            f'La partícula pesada sedimenta {razon_velocidades:,.2f} veces más rápido que la de ganga '
            'del mismo tamaño. Cuanto mayor sea esta razón, más nítida será la separación en jigs, '
            'espirales y mesas.')})

    return _vista(plantilla, resultados=resultados, notas=notas, graficos={
        'criterio': grafico_criterio(resultados),
        'velocidades': grafico_velocidades(resultados),
    })


def grafico_criterio(r):
    """Criterio de concentración en función de la densidad del mineral pesado."""
    rho = np.linspace(max(r['rho_l'] + 0.05, r['rho_f'] + 0.1), max(r['rho_h'] * 1.4, r['rho_l'] + 4), 70)
    cc = (rho - r['rho_f']) / (r['rho_l'] - r['rho_f'])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rho, y=cc, mode='lines', line=dict(width=3), name='CC',
                             hovertemplate='ρ = %{x:.2f} g/cm³<br>CC = %{y:.2f}<extra></extra>'))
    for umbral, texto, color in ((2.5, 'CC = 2,5 · fácil', '#059669'),
                                 (1.75, 'CC = 1,75', '#d97706'),
                                 (1.25, 'CC = 1,25 · límite', '#dc2626')):
        fig.add_hline(y=umbral, line_dash='dash', line_width=1.4, line_color=color,
                      annotation_text=texto, annotation_position='right')
    fig.add_trace(go.Scatter(x=[r['rho_h']], y=[r['criterio']], mode='markers+text',
                             name='Caso actual', marker=dict(size=14, symbol='diamond'),
                             text=['Actual'], textposition='top center'))
    fig.update_layout(
        title='Criterio de concentración según la densidad del mineral',
        xaxis=dict(title='Densidad del mineral pesado (g/cm³)'),
        yaxis=dict(title='Criterio de concentración CC'),
        hovermode='x unified',
    )
    return _fig(fig)


def grafico_velocidades(r):
    """Velocidad terminal frente al tamaño para el mineral y para la ganga."""
    d_mm = np.logspace(math.log10(max(0.01, r['tamano'] * 0.1)), math.log10(r['tamano'] * 10), 60)
    d_m = d_mm / 1000
    mu = r['viscosidad']
    rho_f = r['rho_f'] * 1000

    def vt(rho_s):
        dr = (rho_s - r['rho_f']) * 1000
        stokes = G * d_m ** 2 * dr / (18 * mu)
        newton = 1.74 * np.sqrt(G * d_m * dr / rho_f)
        return np.minimum(stokes, newton)      # transición suave entre regímenes

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d_mm, y=vt(r['rho_h']) * 1000, mode='lines', name='Mineral pesado',
                             line=dict(width=3),
                             hovertemplate='d = %{x:.3g} mm<br>v = %{y:.3g} mm/s<extra></extra>'))
    fig.add_trace(go.Scatter(x=d_mm, y=vt(r['rho_l']) * 1000, mode='lines', name='Ganga liviana',
                             line=dict(width=3, dash='dash'),
                             hovertemplate='d = %{x:.3g} mm<br>v = %{y:.3g} mm/s<extra></extra>'))
    fig.add_vline(x=r['tamano'], line_dash='dot', line_width=1.5,
                  annotation_text='tamaño de diseño', annotation_position='top')
    fig.update_layout(
        title='Velocidad terminal de sedimentación según el tamaño',
        xaxis=dict(title='Tamaño de partícula (mm)', type='log'),
        yaxis=dict(title='Velocidad terminal (mm/s)', type='log'),
        hovermode='x unified',
    )
    return _fig(fig)


# =============================================================== ALMACENAMIENTO

@bp_dimensionamiento.route('/almacenamiento', methods=['GET', 'POST'])
def almacenamiento():
    plantilla = 'dimensionamiento/almacenamiento.html'
    if request.method != 'POST':
        return _vista(plantilla)

    campos = [
        ('densidad_material', None, 0.1, 8, 'Densidad aparente del material'),
        ('altura_silo', None, 0.1, 100, 'Altura del cuerpo cilíndrico'),
        ('diametro_silo', None, 0.1, 60, 'Diámetro del silo'),
        ('angulo_tolva', 60.0, 20, 89, 'Ángulo de la tolva'),
        ('angulo_reposo', 35.0, 5, 80, 'Ángulo de reposo del material'),
        ('diametro_descarga', 0.0, 0.0, 30, 'Diámetro de la boca de descarga'),
        ('tratamiento', 0.0, 0.0, None, 'Tratamiento de la planta'),
        ('llenado_util', 0.85, 0.3, 1.0, 'Fracción de llenado útil'),
    ]
    v = {}
    for nombre, defecto, mn, mx, etiqueta in campos:
        val, err = _num(nombre, defecto, mn, mx, etiqueta)
        if err:
            return _vista(plantilla, error_mensaje=err)
        v[nombre] = val

    D, H = v['diametro_silo'], v['altura_silo']
    d_desc = v['diametro_descarga'] if v['diametro_descarga'] > 0 else min(0.3 * D, 1.5)
    if d_desc >= D:
        return _vista(plantilla, error_mensaje='La boca de descarga no puede ser mayor que el diámetro del silo.')

    area = math.pi / 4 * D ** 2
    vol_cilindro = area * H

    # Tolva cónica entre D y la boca de descarga, con el ángulo indicado
    altura_tolva = (D - d_desc) / 2 * math.tan(math.radians(v['angulo_tolva']))
    r1, r2 = D / 2, d_desc / 2
    vol_tolva = math.pi * altura_tolva / 3 * (r1 ** 2 + r1 * r2 + r2 ** 2)

    vol_total = vol_cilindro + vol_tolva
    vol_util = vol_total * v['llenado_util']
    capacidad = vol_util * v['densidad_material']       # t
    autonomia = (capacidad / v['tratamiento']) if v['tratamiento'] > 0 else None

    # Presión de pared de Janssen (silo esbelto)
    k = 0.4          # relación de presiones lateral/vertical
    mu_pared = 0.45  # coeficiente de fricción material-acero
    rho = v['densidad_material'] * 1000                 # kg/m³
    radio_hidraulico = D / 4
    z = H
    exponente = -mu_pared * k * z / radio_hidraulico
    p_vertical = (rho * G * radio_hidraulico) / (mu_pared * k) * (1 - math.exp(exponente))
    p_lateral = k * p_vertical
    p_hidrostatica = rho * G * z

    esbeltez = H / D
    flujo_masico = v['angulo_tolva'] >= (v['angulo_reposo'] + 15)

    resultados = {
        'D': D, 'H': H, 'area': area,
        'angulo_tolva': v['angulo_tolva'], 'angulo_reposo': v['angulo_reposo'],
        'diametro_descarga': d_desc, 'altura_tolva': altura_tolva, 'altura_total': H + altura_tolva,
        'vol_cilindro': vol_cilindro, 'vol_tolva': vol_tolva, 'vol_total': vol_total,
        'vol_util': vol_util, 'llenado_util': v['llenado_util'],
        'densidad': v['densidad_material'], 'capacidad': capacidad,
        'tratamiento': v['tratamiento'], 'autonomia': autonomia,
        'p_vertical': p_vertical / 1000, 'p_lateral': p_lateral / 1000,
        'p_hidrostatica': p_hidrostatica / 1000,
        'reduccion_janssen': (1 - p_vertical / p_hidrostatica) * 100 if p_hidrostatica else 0,
        'esbeltez': esbeltez, 'flujo_masico': flujo_masico,
        'pasos': [
            f'Área de la sección: A = π·D²/4 = π×{D:g}²/4 = {area:,.3f} m²',
            f'Volumen del cilindro: V = A·H = {area:,.3f} × {H:g} = {vol_cilindro:,.2f} m³',
            f'Altura de la tolva con θ = {v["angulo_tolva"]:g}°: h = (D − d)/2 × tan θ = {altura_tolva:,.2f} m',
            f'Volumen de la tolva (tronco de cono): {vol_tolva:,.2f} m³',
            f'Volumen útil ({v["llenado_util"]:.0%} del total): {vol_util:,.2f} m³',
            f'Capacidad: M = V_útil × ρ = {vol_util:,.2f} × {v["densidad_material"]:g} = {capacidad:,.2f} t',
            (f'Autonomía: t = M / tratamiento = {capacidad:,.2f} / {v["tratamiento"]:g} = {autonomia:,.2f} h'
             if autonomia else ''),
            f'Presión vertical de Janssen en la base: {p_vertical / 1000:,.2f} kPa '
            f'(la hidrostática equivalente sería {p_hidrostatica / 1000:,.2f} kPa)',
        ],
    }

    notas = []
    if flujo_masico:
        notas.append({'color': 'success', 'texto': (
            f'El ángulo de tolva ({v["angulo_tolva"]:g}°) supera al de reposo ({v["angulo_reposo"]:g}°) '
            'con margen suficiente: se espera flujo másico, sin zonas muertas.')})
    else:
        notas.append({'color': 'warning', 'texto': (
            f'El ángulo de tolva ({v["angulo_tolva"]:g}°) no supera al de reposo ({v["angulo_reposo"]:g}°) '
            'en al menos 15°. Riesgo de flujo en embudo, formación de arcos y zonas de material estancado. '
            'Considera una tolva más empinada o un revestimiento de baja fricción.')})

    if esbeltez < 1.5:
        notas.append({'color': 'info', 'texto': (
            f'Con H/D = {esbeltez:,.2f} el recipiente es una tolva ancha más que un silo esbelto. '
            'La reducción de presión por fricción de pared (efecto Janssen) es menor en esta geometría.')})
    else:
        notas.append({'color': 'info', 'texto': (
            f'Con H/D = {esbeltez:,.2f} se comporta como silo esbelto: la fricción con la pared absorbe '
            f'el {resultados["reduccion_janssen"]:,.1f} % de la carga respecto al caso hidrostático.')})

    if autonomia is not None:
        if autonomia < 4:
            notas.append({'color': 'warning', 'texto': (
                f'La autonomía de {autonomia:,.1f} h es corta. Las tolvas de alimentación a planta '
                'suelen dimensionarse para 8–24 h de operación continua.')})
        else:
            notas.append({'color': 'success', 'texto': (
                f'La autonomía de {autonomia:,.1f} h permite absorber paradas del circuito de '
                'alimentación sin detener la planta.')})

    return _vista(plantilla, resultados=resultados, notas=notas, graficos={
        'capacidad': grafico_capacidad_silo(resultados),
        'presion': grafico_presion_janssen(resultados),
    })


def grafico_capacidad_silo(r):
    """Capacidad almacenada en función de la altura del cuerpo cilíndrico."""
    h = np.linspace(max(0.5, r['H'] * 0.25), r['H'] * 2, 60)
    cap = (r['area'] * h + r['vol_tolva']) * r['llenado_util'] * r['densidad']

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=h, y=cap, mode='lines', line=dict(width=3), name='Capacidad',
                             hovertemplate='H = %{x:.2f} m<br>Capacidad = %{y:,.1f} t<extra></extra>'))
    fig.add_trace(go.Scatter(x=[r['H']], y=[r['capacidad']], mode='markers+text',
                             name='Diseño', marker=dict(size=14, symbol='diamond'),
                             text=['Diseño'], textposition='top center'))
    if r['tratamiento']:
        for horas, etiqueta in ((8, '8 h'), (12, '12 h'), (24, '24 h')):
            fig.add_hline(y=r['tratamiento'] * horas, line_dash='dot', line_width=1.2,
                          annotation_text=f'{etiqueta} de autonomía', annotation_position='right')
    fig.update_layout(
        title='Capacidad del silo según la altura del cilindro',
        xaxis=dict(title='Altura del cuerpo cilíndrico H (m)'),
        yaxis=dict(title='Capacidad almacenada (t)'),
        hovermode='x unified',
    )
    return _fig(fig)


def grafico_presion_janssen(r):
    """Perfil de presión vertical con la profundidad: Janssen frente a hidrostática."""
    z = np.linspace(0, r['H'], 60)
    rho = r['densidad'] * 1000
    rh = r['D'] / 4
    k, mu = 0.4, 0.45
    p_j = (rho * G * rh) / (mu * k) * (1 - np.exp(-mu * k * z / rh)) / 1000
    p_h = rho * G * z / 1000

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=p_j, y=z, mode='lines', name='Janssen (con fricción de pared)',
                             line=dict(width=3),
                             hovertemplate='p = %{x:.1f} kPa<br>z = %{y:.2f} m<extra></extra>'))
    fig.add_trace(go.Scatter(x=p_h, y=z, mode='lines', name='Hidrostática (sin fricción)',
                             line=dict(width=2, dash='dash'),
                             hovertemplate='p = %{x:.1f} kPa<br>z = %{y:.2f} m<extra></extra>'))
    fig.update_layout(
        title='Presión vertical sobre el material almacenado',
        xaxis=dict(title='Presión vertical (kPa)'),
        yaxis=dict(title='Profundidad desde la superficie (m)', autorange='reversed'),
        hovermode='y unified',
    )
    return _fig(fig)


# =============================================================== ÍNDICE

@bp_dimensionamiento.route('/')
def dimensionamiento():
    return render_template('dimensionamiento/dimensionamiento.html')
