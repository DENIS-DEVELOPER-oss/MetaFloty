# MetaFlotPy

Plataforma web de cálculos para el procesamiento de minerales. Cubre la cadena
completa de una planta concentradora, desde el análisis granulométrico de la
alimentación hasta la valorización comercial del concentrado.

Cada módulo muestra la fórmula aplicada, la sustitución numérica paso a paso y
un esquema de referencia del equipo o circuito con las variables señaladas
sobre el dibujo.

---

## Módulos

| | Módulo | Qué resuelve | Modelos |
|---|---|---|---|
| I | **Granulometría** | Curvas de distribución, tamaños d₁₀–d₉₀, coeficientes Cu y Cc, cierre de masa | Gates-Gaudin-Schuhmann, Rosin-Rammler, regresión empírica |
| II | **Balance de masa** | Corriente desconocida y carga circulante de circuitos de molienda | Directo, inverso, SABC-1, SABC-2 |
| III | **Balance metalúrgico** | Recuperación, razón de concentración, distribución del metal y conciliación de la ley de cabeza | Fórmula de dos productos; ley de cabeza ensayada vs calculada |
| IV | **Dimensionamiento** | Molinos, hidrociclones, separadores gravimétricos y silos | Bond-Rowland, Plitt (1976), Taggart, Stokes/Newton, Janssen |
| V | **Valorización** | Liquidación comercial completa hasta el NSR | Metal pagable, maquila (TC), refinación (RC), penalidades y flete |
| VI | **Utilitarios** | Densidad de pulpa, equivalencias de ley, dosificación de reactivos, tiempo de residencia y conversores | — |

---

## Características

- **Cálculo sin recargar la página.** El formulario se envía en segundo plano y
  solo se sustituye el bloque de resultados.
- **Esquema de referencia por módulo**, en SVG, adaptado al tema claro u oscuro.
- **Tabla de mallas editable**: series ASTM y Tyler, filas dinámicas, verificación
  de masa en vivo y pegado directo de columnas desde Excel.
- **Responsiva**: verificada de 360 px a escritorio, con objetivos táctiles
  cómodos y campos que no disparan el zoom automático en iOS.
- **Exportación** de cualquier tabla a CSV e impresión o guardado en PDF.
- **Sin base de datos**: todos los cálculos se resuelven en memoria durante la
  petición.

---

## Ejecución local

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python main.py
```

Disponible en <http://127.0.0.1:5000>.

Cada módulo trae un botón **Ejemplo** que rellena el formulario con un caso
realista para probarlo sin datos propios.

---

## Despliegue

Ver [`despliegue/README.md`](despliegue/README.md). Incluye configuración lista
para **Linux** (Nginx + gunicorn + systemd) y para **Windows** (Nginx o IIS +
waitress como servicio).

En producción es obligatorio definir `METAFLOTPY_SECRET_KEY`: la aplicación se
niega a arrancar sin ella. Ver [`.env.ejemplo`](.env.ejemplo).

---

## Estructura

```
app/
  __init__.py          fábrica de la aplicación, filtros y cabeceras
  tamizado/            módulo I
  balance_masa/        módulo II
  balance_metalurgico/ módulo III
  dimensionamiento/    módulo IV
  valorizacion/        módulo V
  utilitarios/         módulo VI
  principal/           inicio y guía de uso
  templates/           plantillas Jinja; _esquemas.html contiene los diagramas
  static/css|js        sistema de diseño y núcleo de interfaz
despliegue/            configuración para servidor propio
main.py                entrada de desarrollo
wsgi.py                entrada de producción
```

---

## Alcance de los resultados

Los cálculos son estimaciones de **ingeniería conceptual**: sirven para
prediseño, comparación de alternativas y docencia. Los modelos empleados son
empíricos y fueron calibrados en rangos concretos. El diseño de detalle exige
ensayos del mineral y las curvas de desempeño del fabricante del equipo.

En la valorización, los términos comerciales (TC, RC, deducciones y
penalidades) se negocian caso a caso: los valores precargados son referencias
de mercado y deben reemplazarse por los del contrato real.
