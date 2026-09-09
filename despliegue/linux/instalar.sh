#!/usr/bin/env bash
# Instalación de MetaFlotPy en un servidor Linux (Debian/Ubuntu o RHEL/Rocky).
#
#   sudo bash despliegue/linux/instalar.sh
#
# Con dominio propio:
#   sudo METAFLOTPY_DOMINIO=metaflotpy.tudominio.pe bash despliegue/linux/instalar.sh
#
# Sin dominio la aplicación queda accesible por la IP del servidor en HTTP.
# El certificado TLS se emite después con certbot; el script indica cómo.

set -euo pipefail

RAIZ="${METAFLOTPY_RAIZ:-/opt/metaflotpy}"
USUARIO="${METAFLOTPY_USUARIO:-metaflotpy}"
REPO="${METAFLOTPY_REPO:-https://github.com/DENIS-DEVELOPER-oss/MetaFloty.git}"
DOMINIO="${METAFLOTPY_DOMINIO:-}"          # vacío = acceso por IP

aviso() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()    { printf '\033[1;32m    %s\033[0m\n' "$*"; }
error() { printf '\n\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || error "Ejecuta el script como root (sudo)."

aviso "1/7 · Dependencias del sistema"
if command -v apt-get >/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq python3 python3-venv python3-pip nginx git curl
elif command -v dnf >/dev/null; then
    dnf install -y -q python3 python3-pip nginx git curl
else
    error "Gestor de paquetes no reconocido: instala python3, python3-venv, nginx, git y curl a mano."
fi
ok "listas"

aviso "2/7 · Usuario de servicio '$USUARIO'"
if id -u "$USUARIO" >/dev/null 2>&1; then
    ok "ya existía"
else
    useradd --system --create-home --shell /usr/sbin/nologin "$USUARIO"
    ok "creado"
fi

aviso "3/7 · Código fuente en $RAIZ/app"
mkdir -p "$RAIZ"
if [[ -d "$RAIZ/app/.git" ]]; then
    git config --global --add safe.directory "$RAIZ/app" 2>/dev/null || true
    git -C "$RAIZ/app" pull --ff-only
    ok "actualizado desde el repositorio"
else
    git clone --depth 1 "$REPO" "$RAIZ/app"
    ok "clonado"
fi
[[ -f "$RAIZ/app/wsgi.py" ]] || error "No se encuentra $RAIZ/app/wsgi.py: revisa la ruta del proyecto."

aviso "4/7 · Entorno virtual y dependencias"
python3 -m venv "$RAIZ/venv"
"$RAIZ/venv/bin/pip" install --quiet --upgrade pip wheel
"$RAIZ/venv/bin/pip" install --quiet -r "$RAIZ/app/requirements.txt"
ok "$("$RAIZ/venv/bin/python" -V) con las dependencias instaladas"

aviso "5/7 · Variables de entorno en /etc/metaflotpy.env"
if [[ -f /etc/metaflotpy.env ]]; then
    ok "ya existía: se conserva la clave actual"
else
    CLAVE=$("$RAIZ/venv/bin/python" -c 'import secrets; print(secrets.token_hex(32))')
    cat > /etc/metaflotpy.env <<ENV
METAFLOTPY_ENTORNO=produccion
METAFLOTPY_SECRET_KEY=$CLAVE
METAFLOTPY_TRAS_PROXY=1
METAFLOTPY_WORKERS=3
ENV
    ok "clave de sesión generada"
fi
chmod 600 /etc/metaflotpy.env
chown root:root /etc/metaflotpy.env
chown -R "$USUARIO":"$USUARIO" "$RAIZ"

aviso "6/7 · Servicio systemd"
sed "s#/opt/metaflotpy#$RAIZ#g; s#^User=metaflotpy#User=$USUARIO#; s#^Group=metaflotpy#Group=$USUARIO#" \
    "$RAIZ/app/despliegue/linux/metaflotpy.service" > /etc/systemd/system/metaflotpy.service
systemctl daemon-reload
systemctl enable --quiet metaflotpy
systemctl restart metaflotpy
sleep 4
if ! systemctl is-active --quiet metaflotpy; then
    journalctl -u metaflotpy -n 40 --no-pager
    error "El servicio no arrancó. Revisa el registro de arriba."
fi
curl -fsS --max-time 10 http://127.0.0.1:8000/salud >/dev/null \
    || error "El servicio arrancó pero /salud no responde."
ok "activo y respondiendo en 127.0.0.1:8000"

aviso "7/7 · Nginx"
CONF=$(mktemp)

# ¿El dominio ya tiene certificado emitido? Entonces se sirve HTTPS de
# entrada, sin pasar de nuevo por certbot.
CERT_DIR="/etc/letsencrypt/live/$DOMINIO"
CON_TLS=0
if [[ -n "$DOMINIO" && -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
    CON_TLS=1
fi

if [[ $CON_TLS -eq 1 ]]; then
    sed "s#/opt/metaflotpy#$RAIZ#g" \
        "$RAIZ/app/despliegue/linux/nginx-metaflotpy-https.conf" > "$CONF"
    sed -i "s#server_name metaflotpy.ejemplo.pe;#server_name $DOMINIO;#g" "$CONF"
    sed -i "s#/etc/ssl/metaflotpy/fullchain.pem#$CERT_DIR/fullchain.pem#" "$CONF"
    sed -i "s#/etc/ssl/metaflotpy/privkey.pem#$CERT_DIR/privkey.pem#" "$CONF"
    ok "sitio HTTPS para $DOMINIO reutilizando el certificado existente"
elif [[ -n "$DOMINIO" ]]; then
    sed "s#/opt/metaflotpy#$RAIZ#g" "$RAIZ/app/despliegue/linux/nginx-metaflotpy.conf" > "$CONF"
    sed -i "s#server_name metaflotpy.ejemplo.pe;#server_name $DOMINIO;#" "$CONF"
    ok "sitio HTTP para $DOMINIO (el certificado se emite después con certbot)"
else
    sed "s#/opt/metaflotpy#$RAIZ#g" "$RAIZ/app/despliegue/linux/nginx-metaflotpy.conf" > "$CONF"
    # Sin dominio: se atiende cualquier nombre y se desactiva el sitio por
    # defecto de Nginx, que si no capturaría las peticiones a la IP.
    sed -i "s#server_name metaflotpy.ejemplo.pe;#server_name _;#" "$CONF"
    sed -i "0,/listen 80;/s##listen 80 default_server;#" "$CONF"
    sed -i "0,/listen \[::\]:80;/s##listen [::]:80 default_server;#" "$CONF"
    rm -f /etc/nginx/sites-enabled/default
    ok "sitio configurado para acceso por IP"
fi

mkdir -p /var/www/certbot
if [[ -d /etc/nginx/sites-available ]]; then
    install -m 644 "$CONF" /etc/nginx/sites-available/metaflotpy
    ln -sf /etc/nginx/sites-available/metaflotpy /etc/nginx/sites-enabled/metaflotpy
else
    install -m 644 "$CONF" /etc/nginx/conf.d/metaflotpy.conf
fi
rm -f "$CONF"

nginx -t || error "La configuración de Nginx no es válida (ver el detalle arriba)."
systemctl enable --quiet nginx
systemctl reload nginx || systemctl restart nginx
ok "Nginx recargado"

# --- Comprobación de extremo a extremo ---
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [[ $CON_TLS -eq 1 ]]; then
    PRUEBA=(curl -fsS --max-time 10 --resolve "$DOMINIO:443:127.0.0.1" "https://$DOMINIO/salud")
else
    PRUEBA=(curl -fsS --max-time 10 -H "Host: ${DOMINIO:-localhost}" http://127.0.0.1/salud)
fi
# Tras un reload, los procesos nuevos de Nginx tardan un instante en tomar
# la configuración; mientras tanto los viejos siguen sirviendo la anterior.
# Por eso se reintenta en lugar de dar por fallido al primer intento.
LOGRADO=0
for _ in $(seq 1 10); do
    if "${PRUEBA[@]}" >/dev/null 2>&1; then LOGRADO=1; break; fi
    sleep 2
done
if [[ $LOGRADO -eq 1 ]]; then
    ok "la aplicación responde a través de Nginx"
else
    error "Nginx no está entregando la aplicación. Revisa /var/log/nginx/metaflotpy.error.log"
fi

echo
echo "────────────────────────────────────────────────────────────"
echo " MetaFlotPy instalado y funcionando."
echo
if [[ $CON_TLS -eq 1 ]]; then
    echo "   https://$DOMINIO"
    echo
    echo " El certificado ya existía y se reutilizó: no hace falta certbot."
    echo " Su renovación automática (certbot.timer) sigue funcionando."
elif [[ -n "$DOMINIO" ]]; then
    echo "   http://$DOMINIO"
    echo
    echo " Para activar HTTPS, con el dominio ya apuntando a este"
    echo " servidor, ejecuta:"
    echo
    echo "     sudo apt install -y certbot python3-certbot-nginx"
    echo "     sudo certbot --nginx -d $DOMINIO"
    echo
    echo " certbot añade el bloque HTTPS y la redirección por sí solo."
else
    echo "   http://${IP:-<IP-del-servidor>}"
    echo
    echo " Estás sirviendo por HTTP sin cifrar. Cuando tengas un"
    echo " dominio apuntando aquí, vuelve a ejecutar el script así:"
    echo
    echo "     sudo METAFLOTPY_DOMINIO=tu-dominio.pe bash $RAIZ/app/despliegue/linux/instalar.sh"
    echo "     sudo apt install -y certbot python3-certbot-nginx"
    echo "     sudo certbot --nginx -d tu-dominio.pe"
fi
echo
echo " Comandos útiles:"
echo "     systemctl status metaflotpy"
echo "     journalctl -u metaflotpy -f"
echo "     systemctl restart metaflotpy      # tras actualizar el código"
echo "────────────────────────────────────────────────────────────"
