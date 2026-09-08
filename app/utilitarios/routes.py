
from flask import Blueprint, render_template

bp_utilitarios = Blueprint('utilitarios', __name__)

@bp_utilitarios.route('/')
def utilitarios():
    return render_template('utilitarios/utilitarios.html')

@bp_utilitarios.route('/conversores')
def conversores():
    return render_template('utilitarios/conversores.html')
