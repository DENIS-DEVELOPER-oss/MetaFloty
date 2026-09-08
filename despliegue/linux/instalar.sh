#!/usr/bin/env bash
# Instalación de MetaFlotPy en un servidor Linux (Debian/Ubuntu o RHEL/Rocky).
#
#   sudo bash despliegue/linux/instalar.sh
#
# Deja el servicio corriendo en 127.0.0.1:8000 detrás de Nginx.
# No toca el certificado TLS: eso se hace con certbot al final.

set -euo pipefail

RAIZ="${METAFLOTPY_RAIZ:-/opt/metaflotpy}"
USUARIO="${METAFLOTPY_USUARIO:-metaflotpy}"
REPO="${METAFLOTPY_REPO:-}"          # URL del repositorio git
DOMINIO="${METAFLOTPY_DOMINIO:-metaflotpy.ejemplo.pe}"

aviso() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
error() { printf '\n\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || error "Ejecuta el script como root (sudo)."

aviso "1/7 · Dependencias del sistema"
if command -v apt-get >/dev/null; then
    apt-get update -qq
    apt-get install -y python3 python3-venv python3-pip nginx git
elif command -v dnf >/dev/null; then
    dnf install -y python3 python3-pip nginx git
else
    error "Gestor de paquetes no reconocido: instala python3, python3-venv, nginx y git a mano."
fi

aviso "2/7 · Usuario de servicio '$USUARIO'"
id -u "$USUARIO" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$USUARIO"

aviso "3/7 · Código fuente en $RAIZ/app"
mkdir -p "$RAIZ"
if [[ -n "$REPO" ]]; then
    if [[ -d "$RAIZ/app/.git" ]]; then
        git -C "$RAIZ/app" pull --ff-only
    else
        git clone "$REPO" "$RAIZ/app"
    fi
else
    [[ -d "$RAIZ/app" ]] || error "Copia el proyecto en $RAIZ/app, o exporta METAFLOTPY_REPO con la URL del repositorio."
fi
[[ -f "$RAIZ/app/wsgi.py" ]] || error "No se encuentra $RAIZ/app/wsgi.py: revisa la ruta del proyecto."

aviso "4/7 · Entorno virtual y dependencias"
python3 -m venv "$RAIZ/venv"
"$RAIZ/venv/bin/pip" install --upgrade pip wheel
"$RAIZ/venv/bin/pip" install -r "$RAIZ/app/requirements.txt"

aviso "5/7 · Variables de entorno en /etc/metaflotpy.env"
if [[ ! -f /etc/metaflotpy.env ]]; then
    CLAVE=$("$RAIZ/venv/bin/python" -c 'import secrets; print(secrets.token_hex(32))')
    cat > /etc/metaflotpy.env <<ENV
METAFLOTPY_ENTORNO=produccion
METAFLOTPY_SECRET_KEY=$CLAVE
METAFLOTPY_TRAS_PROXY=1
METAFLOTPY_WORKERS=3
ENV
    echo "   Clave de sesión generada."
else
    echo "   Ya existía: se conserva."
fi
chmod 600 /etc/metaflotpy.env
chown root:root /etc/metaflotpy.env
chown -R "$USUARIO":"$USUARIO" "$RAIZ"

aviso "6/7 · Servicio systemd"
sed "s#/opt/metaflotpy#$RAIZ#g; s#User=metaflotpy#User=$USUARIO#; s#Group=metaflotpy#Group=$USUARIO#" \
    "$RAIZ/app/despliegue/linux/metaflotpy.service" > /etc/systemd/system/metaflotpy.service
systemctl daemon-reload
systemctl enable --now metaflotpy
sleep 3
systemctl is-active --quiet metaflotpy || { journalctl -u metaflotpy -n 40 --no-pager; error "El servicio no arrancó."; }

aviso "7/7 · Nginx"
sed "s#/opt/metaflotpy#$RAIZ#g; s#metaflotpy.ejemplo.pe#$DOMINIO#g" \
    "$RAIZ/app/despliegue/linux/nginx-metaflotpy.conf" > /etc/nginx/sites-available/metaflotpy 2>/dev/null \
    || sed "s#/opt/metaflotpy#$RAIZ#g; s#metaflotpy.ejemplo.pe#$DOMINIO#g" \
       "$RAIZ/app/despliegue/linux/nginx-metaflotpy.conf" > /etc/nginx/conf.d/metaflotpy.conf
[[ -d /etc/nginx/sites-enabled ]] && ln -sf /etc/nginx/sites-available/metaflotpy /etc/nginx/sites-enabled/metaflotpy
mkdir -p /var/www/certbot

echo
echo "Comprobación local del servicio:"
curl -fsS http://127.0.0.1:8000/salud && echo

cat <<FIN

────────────────────────────────────────────────────────────
Servicio instalado y corriendo.

Falta el certificado TLS. Con el dominio ya apuntando a este
servidor, ejecuta:

    sudo certbot --nginx -d $DOMINIO

(Nginx aún no arrancará con HTTPS hasta tener el certificado;
 certbot ajusta la configuración por ti.)

Comandos útiles:
    systemctl status metaflotpy
    journalctl -u metaflotpy -f
    systemctl restart metaflotpy      # tras actualizar el código
────────────────────────────────────────────────────────────
FIN
