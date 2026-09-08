from flask_wtf import FlaskForm
from wtforms import FloatField, SelectField, SubmitField
from wtforms.validators import NumberRange, Optional

CIRCUITOS = [
    ('directo', 'Circuito cerrado directo — F = P + R'),
    ('inverso', 'Circuito cerrado inverso — F + R = P'),
    ('sabc1', 'Circuito SABC-1 — SAG + bolas con clasificación'),
    ('sabc2', 'Circuito SABC-2 — SAG con harnero y rechazo a bolas'),
]


class FormularioBalanceMasa(FlaskForm):
    """Un único juego de corrientes; la vista decide cuáles aplican al circuito."""

    tipo_circuito = SelectField('Tipo de circuito', choices=CIRCUITOS, default='directo')

    f_flujo = FloatField('F · Alimentación fresca (t/h)',
                         validators=[Optional(), NumberRange(min=0)],
                         render_kw={'step': '0.01', 'min': '0', 'placeholder': '250'})

    p_flujo = FloatField('P · Producto final (t/h)',
                         validators=[Optional(), NumberRange(min=0)],
                         render_kw={'step': '0.01', 'min': '0', 'placeholder': '250'})

    r_flujo = FloatField('R · Carga circulante (t/h)',
                         validators=[Optional(), NumberRange(min=0)],
                         render_kw={'step': '0.01', 'min': '0', 'placeholder': '625'})

    s_flujo = FloatField('S · Producto del molino SAG (t/h)',
                         validators=[Optional(), NumberRange(min=0)],
                         render_kw={'step': '0.01', 'min': '0', 'placeholder': '250'})

    b_flujo = FloatField('B · Descarga del molino de bolas (t/h)',
                         validators=[Optional(), NumberRange(min=0)],
                         render_kw={'step': '0.01', 'min': '0', 'placeholder': '875'})

    calcular = SubmitField('Calcular balance de masa')
