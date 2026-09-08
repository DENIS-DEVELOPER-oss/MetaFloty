from flask_wtf import FlaskForm
from wtforms import FloatField, SelectField, SubmitField
from wtforms.validators import NumberRange, Optional

TIPOS_BALANCE = [
    ('1_concentrado', 'Un concentrado — F = C + T'),
    ('2_concentrados', 'Dos concentrados — F = C₁ + C₂ + T'),
    ('3_concentrados', 'Tres concentrados — F = C₁ + C₂ + C₃ + T'),
]

UNIDADES_LEY = [
    ('%', 'Porcentaje (%) — Cu, Pb, Zn, Fe'),
    ('g/t', 'Gramos por tonelada (g/t) — Au, Ag'),
    ('oz/t', 'Onzas por tonelada (oz/t)'),
]

# Ley de cabeza sobre la que se calculan recuperación y distribución
BASES_LEY = [
    ('calculada', 'Ley de cabeza calculada — reconstituida de los productos'),
    ('ensayada', 'Ley de cabeza ensayada — muestreo directo de la alimentación'),
]


def _masa(etiqueta, ph):
    return FloatField(etiqueta, validators=[Optional(), NumberRange(min=0)],
                      render_kw={'step': '0.01', 'min': '0', 'placeholder': ph})


def _ley(etiqueta, ph):
    return FloatField(etiqueta, validators=[Optional(), NumberRange(min=0)],
                      render_kw={'step': '0.001', 'min': '0', 'placeholder': ph})


class FormularioBalanceMetalurgico(FlaskForm):
    tipo_balance = SelectField('Tipo de balance', choices=TIPOS_BALANCE, default='1_concentrado')
    unidad_ley = SelectField('Unidad de ley', choices=UNIDADES_LEY, default='%')
    base_ley = SelectField('Ley de cabeza para los resultados', choices=BASES_LEY, default='calculada')

    f_masa = _masa('F · Masa de alimentación', '1000')
    f_ley = _ley('f · Ley de cabeza ensayada', '1.2')

    c1_masa = _masa('C₁ · Masa de concentrado 1', '')
    c1_ley = _ley('c₁ · Ley de concentrado 1', '28')

    c2_masa = _masa('C₂ · Masa de concentrado 2', '')
    c2_ley = _ley('c₂ · Ley de concentrado 2', '55')

    c3_masa = _masa('C₃ · Masa de concentrado 3', '')
    c3_ley = _ley('c₃ · Ley de concentrado 3', '45')

    t_masa = _masa('T · Masa de relave', '')
    t_ley = _ley('t · Ley de relave', '0.08')

    calcular = SubmitField('Calcular balance metalúrgico')
