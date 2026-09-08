# Despliegue de MetaFlotPy en servidor propio

Arquitectura en producción:

```
Internet ──HTTPS──> Nginx (o IIS) ──HTTP──> gunicorn / waitress ──> wsgi:app
                         │                        127.0.0.1:8000
                         └── /static/  servido directamente desde disco
```

El servidor WSGI escucha **solo en 127.0.0.1**: al exterior únicamente se
expone el proxy inverso, que es quien termina el TLS.

---

## 0 · Requisitos

| | |
|---|---|
| Python | 3.10 o superior (probado en 3.12) |
| Memoria | 1,5 GB libres (numpy, pandas, scipy y plotly ocupan ~350 MB por proceso) |
| Disco | 1 GB |
| Red | puertos 80 y 443 abiertos; el 8000 queda solo local |

La aplicación **no usa base de datos** y **no escribe en disco**: todos los
cálculos se resuelven en memoria durante la petición. Eso simplifica el
respaldo (basta el código) y permite reiniciar el servicio sin pérdida de datos.

---

## 1 · Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `METAFLOTPY_ENTORNO` | sí | `produccion` activa cookies seguras, HSTS y caché de estáticos |
| `METAFLOTPY_SECRET_KEY` | sí | Clave de sesión. **La aplicación se niega a arrancar en producción sin ella** |
| `METAFLOTPY_TRAS_PROXY` | no | `1` si hay proxy inverso delante (por defecto `1` en producción) |
| `METAFLOTPY_WORKERS` | no | Procesos de gunicorn (por defecto 3) |
| `METAFLOTPY_BIND` | no | Dirección de escucha (por defecto `127.0.0.1:8000`) |

Generar la clave:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> La clave **no debe versionarse**. En Linux vive en `/etc/metaflotpy.env`
> (permisos 600); en Windows, en el `.env` de la raíz, que ya está en
> `.gitignore`.

---

## 2 · Linux (Nginx + gunicorn + systemd)

### Instalación asistida

```bash
# 1 · Traer el proyecto
apt update && apt install -y git
git clone https://github.com/DENIS-DEVELOPER-oss/MetaFloty.git /opt/metaflotpy/app

# 2 · Instalar
cd /opt/metaflotpy/app
sudo bash despliegue/linux/instalar.sh                  # acceso por IP

# ...o directamente con dominio:
sudo METAFLOTPY_DOMINIO=tu-dominio.pe bash despliegue/linux/instalar.sh
```

El script instala dependencias, crea el usuario de servicio y el entorno
virtual, genera la clave de sesión, da de alta el servicio systemd, configura
Nginx, valida la configuración con `nginx -t` y comprueba de extremo a extremo
que la aplicación responde a través del proxy antes de darse por terminado.

Es **idempotente**: puedes volver a ejecutarlo para actualizar el código o para
añadir el dominio más adelante. Nunca sobrescribe la clave de sesión existente.

### Certificado TLS

Nginx se instala primero en **HTTP a propósito**: certbot necesita un sitio en
funcionamiento para validar el dominio, y no puede arrancar si la configuración
apunta a certificados que todavía no existen.

Con el DNS ya apuntando al servidor:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tu-dominio.pe
```

certbot añade por sí mismo el bloque 443 con TLS y la redirección desde HTTP.
No hay que editar nada a mano.

> Si ya tienes certificados propios (emitidos por tu institución), usa
> `nginx-metaflotpy-https.conf` en lugar del archivo por defecto y ajusta las
> rutas de `ssl_certificate` y `ssl_certificate_key`.

### Instalación manual, paso a paso

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin metaflotpy
sudo mkdir -p /opt/metaflotpy && cd /opt/metaflotpy
sudo git clone <URL-del-repositorio> app

sudo python3 -m venv venv
sudo ./venv/bin/pip install -r app/requirements.txt

# Clave de sesión
sudo tee /etc/metaflotpy.env >/dev/null <<EOF
METAFLOTPY_ENTORNO=produccion
METAFLOTPY_SECRET_KEY=$(./venv/bin/python -c 'import secrets;print(secrets.token_hex(32))')
METAFLOTPY_TRAS_PROXY=1
EOF
sudo chmod 600 /etc/metaflotpy.env
sudo chown -R metaflotpy:metaflotpy /opt/metaflotpy

# Servicio
sudo cp app/despliegue/linux/metaflotpy.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now metaflotpy

# Nginx
sudo cp app/despliegue/linux/nginx-metaflotpy.conf /etc/nginx/sites-available/metaflotpy
sudo ln -s /etc/nginx/sites-available/metaflotpy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Operación

```bash
systemctl status metaflotpy
journalctl -u metaflotpy -f          # registro en vivo
systemctl restart metaflotpy         # tras actualizar el código
curl -s localhost:8000/salud
```

---

## 3 · Windows (Nginx o IIS + waitress + servicio)

### Prueba manual

```powershell
.\despliegue\windows\servir.ps1
```

Carga el `.env`, arranca waitress en `127.0.0.1:8000` y muestra el registro en
consola. Útil para verificar antes de crear el servicio.

### Servicio permanente

Requiere [NSSM](https://nssm.cc/download) y una consola **como Administrador**:

```powershell
.\despliegue\windows\instalar-servicio.ps1
```

Crea el `.env` con una clave nueva si no existe, registra el servicio con
arranque automático, reinicio ante fallos y rotación de registros en
`C:\ProgramData\MetaFlotPy\logs`, y comprueba `/salud` al finalizar.

Desinstalar:

```powershell
.\despliegue\windows\instalar-servicio.ps1 -Desinstalar
```

### Proxy inverso

- **Nginx para Windows** — usa `despliegue/windows/nginx-metaflotpy.conf`.
  Es la opción recomendada: misma configuración que en Linux.
- **IIS** — usa `despliegue/windows/web.config`. Requiere los módulos
  *URL Rewrite* y *Application Request Routing* con el proxy habilitado
  (IIS → servidor → *Application Request Routing Cache* → *Server Proxy
  Settings* → marcar **Enable proxy**).

### Operación

```powershell
Get-Service MetaFlotPy
Restart-Service MetaFlotPy           # tras actualizar el código
Get-Content C:\ProgramData\MetaFlotPy\logs\metaflotpy.err.log -Tail 50 -Wait
Invoke-RestMethod http://127.0.0.1:8000/salud
```

---

## 4 · Actualizar una versión

```bash
# Linux
cd /opt/metaflotpy/app && sudo -u metaflotpy git pull
sudo /opt/metaflotpy/venv/bin/pip install -r requirements.txt
sudo systemctl restart metaflotpy
```

```powershell
# Windows
cd C:\MetaFlotPy\app; git pull
& <venv>\Scripts\pip.exe install -r requirements.txt
Restart-Service MetaFlotPy
```

> Al publicar cambios de CSS o JavaScript, **sube `VERSION` en
> `app/__init__.py`**. Las plantillas añaden `?v=<VERSION>` a los estáticos,
> de modo que los navegadores descargan la versión nueva pese a la caché de
> 30 días de Nginx.

---

## 5 · Comprobación tras desplegar

```bash
curl -s https://metaflotpy.tudominio.pe/salud
# {"entorno":"produccion","estado":"ok","version":"2.0"}

curl -sI https://metaflotpy.tudominio.pe/ | grep -i strict-transport
# Strict-Transport-Security: max-age=31536000; includeSubDomains
```

Y en el navegador: abrir un módulo, pulsar **Ejemplo** y **Calcular**; los
resultados deben aparecer sin recargar la página y con los gráficos dibujados.

---

## 6 · Notas de seguridad

- La aplicación añade `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy` y, en producción, `HSTS`.
- El tamaño máximo de petición está limitado a 2 MB en la aplicación y en el
  proxy: los formularios son pequeños y así se acota la superficie de abuso.
- No hay autenticación: **cualquiera con la URL puede usar la calculadora**.
  Si el acceso debe restringirse, lo más simple es limitarlo en el proxy
  (por IP con `allow`/`deny`, o con autenticación básica en Nginx).
- Las bibliotecas se instalan con versión fija en `requirements.txt`. Conviene
  revisar actualizaciones de seguridad de Flask y Werkzeug cada cierto tiempo.
