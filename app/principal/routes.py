from flask import Blueprint, render_template

bp_principal = Blueprint('principal', __name__)

@bp_principal.route('/')
def inicio():
    return render_template('principal/inicio.html')

@bp_principal.route('/introduccion')
def introduccion():
    return render_template('principal/introduccion.html')