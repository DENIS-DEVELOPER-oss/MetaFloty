/* ============================================================
   MetaFlotPy · Núcleo de interfaz
   Tema claro/oscuro, sidebar, notificaciones, formato numérico,
   gráficos Plotly con tema, exportación CSV/impresión y
   utilidades de tablas dinámicas.
   ============================================================ */
(function (global) {
  'use strict';

  const MF = {};

  /* ---------- Preferencias persistentes ---------- */
  const LS = {
    get(clave, def) {
      try { const v = localStorage.getItem('mf.' + clave); return v === null ? def : v; }
      catch (e) { return def; }
    },
    set(clave, valor) {
      try { localStorage.setItem('mf.' + clave, valor); } catch (e) { /* modo privado */ }
    }
  };

  /* ---------- Tema ---------- */
  MF.tema = {
    actual() { return document.documentElement.getAttribute('data-tema') || 'claro'; },
    aplicar(tema) {
      document.documentElement.setAttribute('data-tema', tema);
      LS.set('tema', tema);
      const btn = document.getElementById('mf-btn-tema');
      if (btn) {
        btn.innerHTML = tema === 'oscuro' ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon-stars"></i>';
        btn.title = tema === 'oscuro' ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro';
      }
      MF.graficos.retematizarTodos();
    },
    alternar() { this.aplicar(this.actual() === 'oscuro' ? 'claro' : 'oscuro'); }
  };

  /* ---------- Notificaciones ---------- */
  const ICONOS = {
    info: 'bi-info-circle-fill', success: 'bi-check-circle-fill',
    warning: 'bi-exclamation-triangle-fill', danger: 'bi-x-octagon-fill'
  };
  MF.aviso = function (mensaje, tipo, ms) {
    tipo = tipo || 'info';
    let cont = document.querySelector('.mf-toasts');
    if (!cont) {
      cont = document.createElement('div');
      cont.className = 'mf-toasts';
      document.body.appendChild(cont);
    }
    const t = document.createElement('div');
    t.className = 'mf-toast mf-toast--' + tipo;
    t.innerHTML = '<i class="bi ' + (ICONOS[tipo] || ICONOS.info) + '"></i><div></div>' +
                  '<button class="mf-toast__cerrar" aria-label="Cerrar">&times;</button>';
    t.querySelector('div').textContent = mensaje;
    const quitar = () => {
      t.classList.add('saliendo');
      setTimeout(() => t.remove(), 200);
    };
    t.querySelector('.mf-toast__cerrar').addEventListener('click', quitar);
    cont.appendChild(t);
    setTimeout(quitar, ms || 4500);
    return t;
  };

  /* ---------- Formato numérico ---------- */
  MF.fmt = function (valor, decimales) {
    if (valor === null || valor === undefined || valor === '' || isNaN(valor)) return '—';
    const d = decimales === undefined ? 2 : decimales;
    return Number(valor).toLocaleString('es-PE', { minimumFractionDigits: d, maximumFractionDigits: d });
  };
  MF.fmtAuto = function (valor) {
    if (valor === null || valor === undefined || valor === '' || isNaN(valor)) return '—';
    const a = Math.abs(Number(valor));
    if (a === 0) return '0';
    if (a >= 1000) return MF.fmt(valor, 1);
    if (a >= 1) return MF.fmt(valor, 3);
    if (a >= 0.001) return MF.fmt(valor, 4);
    return Number(valor).toExponential(3);
  };
  MF.num = function (v, def) {
    const n = parseFloat(String(v).replace(',', '.'));
    return isNaN(n) ? (def === undefined ? 0 : def) : n;
  };

  /* ---------- Gráficos Plotly con tema ---------- */
  MF.graficos = {
    _registro: new Map(),

    paleta() {
      const cs = getComputedStyle(document.documentElement);
      const v = (n) => cs.getPropertyValue(n).trim();
      return {
        primary: v('--mf-primary') || '#0e7490',
        accent: v('--mf-accent') || '#ea580c',
        success: v('--mf-success') || '#059669',
        warning: v('--mf-warning') || '#d97706',
        danger: v('--mf-danger') || '#dc2626',
        info: v('--mf-info') || '#2563eb',
        texto: v('--mf-text') || '#0f172a',
        tenue: v('--mf-text-muted') || '#64748b',
        borde: v('--mf-border') || '#e2e8f0',
        superficie: v('--mf-surface') || '#ffffff'
      };
    },

    serie() {
      const p = this.paleta();
      return [p.primary, p.accent, p.success, p.info, p.warning, p.danger, '#7c3aed', '#0891b2'];
    },

    layoutBase() {
      const p = this.paleta();
      return {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: {
          family: 'Inter, "Segoe UI", system-ui, sans-serif',
          size: 12,
          color: p.texto
        },
        colorway: this.serie(),
        margin: { l: 62, r: 24, t: 74, b: 56 },
        title: { font: { size: 14, color: p.texto }, x: 0, xanchor: 'left', y: 0.97, yanchor: 'top' },
        hoverlabel: {
          bgcolor: p.superficie, bordercolor: p.borde,
          font: { color: p.texto, size: 12, family: 'Inter, sans-serif' }
        },
        // Leyenda sobre el área de trazado: en gráficos angostos no choca
        // con el título del eje horizontal.
        legend: {
          orientation: 'h', yanchor: 'bottom', y: 1.01, xanchor: 'left', x: 0,
          font: { size: 11, color: p.tenue }, bgcolor: 'rgba(0,0,0,0)'
        },
        xaxis: { gridcolor: p.borde, zerolinecolor: p.borde, linecolor: p.borde, tickfont: { size: 11, color: p.tenue }, title: { font: { size: 12, color: p.tenue } } },
        yaxis: { gridcolor: p.borde, zerolinecolor: p.borde, linecolor: p.borde, tickfont: { size: 11, color: p.tenue }, title: { font: { size: 12, color: p.tenue } } }
      };
    },

    config() {
      return {
        responsive: true,
        displaylogo: false,
        locale: 'es',
        modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
        toImageButtonOptions: { format: 'png', filename: 'metaflotpy-grafico', scale: 2 }
      };
    },

    /* Combina el layout del servidor con el tema del cliente.
       `angosto` = el contenedor es demasiado estrecho para el título de
       Plotly, que se truncaría: la cabecera de la tarjeta ya lo nombra. */
    _fusionar(layoutServidor, angosto) {
      const base = this.layoutBase();
      const out = Object.assign({}, base, layoutServidor || {});
      ['xaxis', 'yaxis', 'xaxis2', 'yaxis2'].forEach((eje) => {
        if (layoutServidor && layoutServidor[eje]) {
          out[eje] = Object.assign({}, base.xaxis, layoutServidor[eje]);
          out[eje].gridcolor = base.xaxis.gridcolor;
          out[eje].linecolor = base.xaxis.linecolor;
          out[eje].zerolinecolor = base.xaxis.zerolinecolor;
          out[eje].tickfont = base.xaxis.tickfont;
          if (out[eje].title && typeof out[eje].title === 'object') {
            out[eje].title.font = base.xaxis.title.font;
          } else if (typeof out[eje].title === 'string') {
            out[eje].title = { text: out[eje].title, font: base.xaxis.title.font };
          }
        }
      });
      if (out.title && typeof out.title === 'string') out.title = { text: out.title };
      if (out.title && typeof out.title === 'object') {
        out.title = Object.assign({}, base.title, out.title);
      }
      out.paper_bgcolor = 'rgba(0,0,0,0)';
      out.plot_bgcolor = 'rgba(0,0,0,0)';
      out.font = base.font;
      out.hoverlabel = base.hoverlabel;
      // Anotaciones y formas heredan color de texto legible
      if (Array.isArray(out.annotations)) {
        out.annotations = out.annotations.map((a) => Object.assign({}, a, {
          font: Object.assign({ color: base.font.color, size: 11 }, a.font || {})
        }));
      }

      if (angosto) {
        out.title = { text: '' };
        out.margin = Object.assign({}, out.margin, { t: 42, l: 48, r: 14, b: 48 });
        out.legend = Object.assign({}, out.legend || {}, { font: { size: 10, color: base.legend.font.color } });
        if (out.xaxis) out.xaxis = Object.assign({}, out.xaxis, { automargin: true });
        if (out.yaxis) out.yaxis = Object.assign({}, out.yaxis, { automargin: true });
      }
      return out;
    },

    /* Un contenedor por debajo de este ancho no admite el título de Plotly */
    _esAngosto(el) { return el && el.clientWidth > 0 && el.clientWidth < 520; },

    /* Dibuja una figura Plotly serializada por el servidor */
    dibujar(idOJson, figuraJson) {
      const el = typeof idOJson === 'string' ? document.getElementById(idOJson) : idOJson;
      if (!el) return null;
      if (!global.Plotly) { console.warn('Plotly no disponible'); return null; }
      let fig = figuraJson;
      if (typeof fig === 'string') {
        try { fig = JSON.parse(fig); } catch (e) { console.error('Figura inválida', e); return null; }
      }
      if (!fig || !fig.data) { return null; }
      this._registro.set(el.id || el, fig);
      const layout = this._fusionar(fig.layout, this._esAngosto(el));
      return global.Plotly.react(el, fig.data, layout, this.config());
    },

    /* Vuelve a pintar todas las figuras registradas al cambiar de tema */
    retematizarTodos() {
      if (!global.Plotly) return;
      this._registro.forEach((fig, clave) => {
        const el = typeof clave === 'string' ? document.getElementById(clave) : clave;
        if (el && el.isConnected) {
          global.Plotly.react(el, fig.data, this._fusionar(fig.layout, this._esAngosto(el)), this.config());
        }
      });
    },

    /* Auto-inicializa <div class="mf-grafico" data-figura="..."> */
    autoIniciar(raiz) {
      const cont = raiz || document;
      cont.querySelectorAll('[data-figura]').forEach((el) => {
        const crudo = el.getAttribute('data-figura');
        if (!crudo || crudo === 'None' || crudo === 'null') {
          el.innerHTML = '<div class="mf-vacio"><i class="bi bi-graph-up"></i><p>Sin datos suficientes para graficar.</p></div>';
          return;
        }
        MF.graficos.dibujar(el, crudo);
      });
    }
  };

  /* ---------- Exportar tabla a CSV ---------- */
  MF.exportarCSV = function (tabla, nombre) {
    const el = typeof tabla === 'string' ? document.querySelector(tabla) : tabla;
    if (!el) { MF.aviso('No se encontró la tabla a exportar.', 'danger'); return; }
    const filas = [];
    el.querySelectorAll('tr').forEach((tr) => {
      const celdas = [];
      tr.querySelectorAll('th,td').forEach((c) => {
        const input = c.querySelector('input,select');
        let txt = input ? input.value : c.innerText;
        txt = String(txt).replace(/\s+/g, ' ').trim().replace(/"/g, '""');
        celdas.push('"' + txt + '"');
      });
      if (celdas.length) filas.push(celdas.join(';'));
    });
    if (!filas.length) { MF.aviso('La tabla está vacía.', 'warning'); return; }
    const blob = new Blob(['﻿' + filas.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (nombre || 'metaflotpy') + '-' + new Date().toISOString().slice(0, 10) + '.csv';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
    MF.aviso('Tabla exportada a CSV.', 'success');
  };

  MF.imprimir = function () { global.print(); };

  /* ---------- Copiar resultados al portapapeles ---------- */
  MF.copiar = function (texto, msg) {
    const ok = () => MF.aviso(msg || 'Copiado al portapapeles.', 'success');
    if (navigator.clipboard && global.isSecureContext) {
      navigator.clipboard.writeText(texto).then(ok, () => MF.aviso('No se pudo copiar.', 'danger'));
    } else {
      const ta = document.createElement('textarea');
      ta.value = texto; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); ok(); } catch (e) { MF.aviso('No se pudo copiar.', 'danger'); }
      ta.remove();
    }
  };

  /* ---------- Validación en vivo de campos numéricos ---------- */
  MF.validarCampo = function (input) {
    const v = input.value.trim();
    const min = input.hasAttribute('min') ? parseFloat(input.min) : -Infinity;
    const max = input.hasAttribute('max') ? parseFloat(input.max) : Infinity;
    const req = input.hasAttribute('required');
    let error = '';
    if (v === '') {
      if (req) error = 'Campo obligatorio.';
    } else {
      const n = parseFloat(v);
      if (isNaN(n)) error = 'Debe ser un número.';
      else if (n < min) error = 'Mínimo ' + min + '.';
      else if (n > max) error = 'Máximo ' + max + '.';
    }
    input.classList.toggle('is-invalid', !!error);
    let fb = input.parentElement.querySelector('.invalid-feedback');
    if (error) {
      if (!fb) {
        fb = document.createElement('div');
        fb.className = 'invalid-feedback d-block';
        input.parentElement.appendChild(fb);
      }
      fb.textContent = error;
    } else if (fb) { fb.remove(); }
    return !error;
  };

  MF.validarFormulario = function (form) {
    let ok = true;
    form.querySelectorAll('input[type="number"]').forEach((i) => {
      if (i.offsetParent === null) return;      // campo oculto: no validar
      if (!MF.validarCampo(i)) ok = false;
    });
    if (!ok) MF.aviso('Revisa los campos marcados en rojo.', 'warning');
    return ok;
  };

  /* ---------- Cálculo sin recargar la página ----------
     El formulario se envía por fetch al mismo endpoint y solo se
     reemplaza el fragmento de resultados de la respuesta. Evita duplicar
     en JavaScript la lógica de presentación que ya resuelve Jinja.      */
  MF.formAjax = function (form) {
    const destinoSel = form.getAttribute('data-ajax') || '#mf-resultados';

    form.addEventListener('submit', function (ev) {
      if (!global.fetch || !global.DOMParser) return;      // navegador antiguo: envío clásico
      ev.preventDefault();

      if (form.hasAttribute('data-validar') && !MF.validarFormulario(form)) return;

      const destino = document.querySelector(destinoSel);
      const boton = form.querySelector('[type="submit"]');
      const textoOriginal = boton ? boton.innerHTML : null;

      if (boton) {
        boton.disabled = true;
        boton.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Calculando…';
      }
      if (destino) destino.classList.add('mf-cargando');

      fetch(form.action || global.location.pathname, {
        method: (form.method || 'POST').toUpperCase(),
        body: new FormData(form),
        headers: { 'X-MetaFlotPy-Fragmento': '1' }
      })
        .then((r) => r.text())
        .then((html) => {
          const doc = new DOMParser().parseFromString(html, 'text/html');
          const nuevo = doc.querySelector(destinoSel);
          const alertas = doc.querySelector('[data-zona-alertas]');
          const zonaAlertas = document.querySelector('[data-zona-alertas]');

          if (zonaAlertas) zonaAlertas.innerHTML = alertas ? alertas.innerHTML : '';

          if (nuevo && destino) {
            destino.replaceWith(nuevo);
            nuevo.classList.add('mf-fade-in');
            MF.graficos.autoIniciar(nuevo);
            MF.formAjax.alActualizar.forEach((fn) => fn(nuevo));
            nuevo.scrollIntoView({ behavior: 'smooth', block: 'start' });
            const err = nuevo.querySelector('[data-error-calculo]');
            if (err) MF.aviso(err.textContent.trim(), 'warning', 6000);
            else if (nuevo.querySelector('[data-hay-resultados]')) MF.aviso('Cálculo completado.', 'success', 2500);
          } else {
            // Sin fragmento reconocible: se recarga por la vía tradicional
            // (form.submit() no dispara el evento 'submit', así que no reentra aquí)
            form.submit();
          }
        })
        .catch((e) => {
          console.error(e);
          MF.aviso('No se pudo completar el cálculo. Revisa tu conexión e inténtalo otra vez.', 'danger');
        })
        .finally(() => {
          if (boton) { boton.disabled = false; boton.innerHTML = textoOriginal; }
          const d = document.querySelector(destinoSel);
          if (d) d.classList.remove('mf-cargando');
        });
    });
  };
  MF.formAjax.alActualizar = [];   // hooks que otros módulos pueden registrar

  /* ---------- Esquemas SVG ----------
     El aviso de «desliza para ver» solo aparece cuando el diagrama
     realmente no cabe en el ancho disponible.                       */
  MF.marcarEsquemasDesplazables = function (raiz) {
    (raiz || document).querySelectorAll('.mf-esquema-wrap').forEach((caja) => {
      const aviso = caja.parentElement && caja.parentElement.querySelector('.mf-esquema-scroll');
      if (aviso) aviso.classList.toggle('visible', caja.scrollWidth > caja.clientWidth + 2);
    });
  };

  /* ---------- Sidebar ---------- */
  function iniciarSidebar() {
    const body = document.body;
    const esMovil = () => global.matchMedia('(max-width: 991.98px)').matches;

    if (LS.get('sidebar', 'ancho') === 'mini' && !esMovil()) body.classList.add('mf-sidebar-mini');

    const alternar = () => {
      if (esMovil()) {
        body.classList.toggle('mf-sidebar-abierto');
      } else {
        body.classList.toggle('mf-sidebar-mini');
        LS.set('sidebar', body.classList.contains('mf-sidebar-mini') ? 'mini' : 'ancho');
        setTimeout(() => { if (global.Plotly) MF.graficos.retematizarTodos(); }, 280);
      }
    };

    const btn = document.getElementById('mf-btn-sidebar');
    if (btn) btn.addEventListener('click', alternar);

    const fondo = document.querySelector('.mf-backdrop');
    if (fondo) fondo.addEventListener('click', () => body.classList.remove('mf-sidebar-abierto'));

    const cerrar = document.getElementById('mf-cerrar-menu');
    if (cerrar) cerrar.addEventListener('click', () => body.classList.remove('mf-sidebar-abierto'));

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') body.classList.remove('mf-sidebar-abierto');
      if (e.key === 'b' && (e.ctrlKey || e.metaKey) && !e.shiftKey) { e.preventDefault(); alternar(); }
    });

    // Cerrar al navegar en móvil
    document.querySelectorAll('.mf-sidebar a[href]').forEach((a) => {
      a.addEventListener('click', () => { if (esMovil()) body.classList.remove('mf-sidebar-abierto'); });
    });
  }

  /* ---------- Marcar enlace activo (soporta subrutas) ---------- */
  function marcarActivo() {
    const ruta = global.location.pathname.replace(/\/+$/, '') || '/';
    let mejor = null, mejorLargo = -1;
    document.querySelectorAll('.mf-sidebar a[href]').forEach((a) => {
      const href = (a.getAttribute('href') || '').replace(/\/+$/, '') || '/';
      if (href === '/' ? ruta === '/' : ruta === href || ruta.startsWith(href + '/')) {
        if (href.length > mejorLargo) { mejor = a; mejorLargo = href.length; }
      }
    });
    if (mejor) {
      mejor.classList.add('activo');
      const sub = mejor.closest('.mf-subnav');
      if (sub) {
        sub.classList.add('show');
        const disparador = document.querySelector('[data-bs-target="#' + sub.id + '"]');
        if (disparador) { disparador.setAttribute('aria-expanded', 'true'); disparador.classList.add('activo'); }
      }
    }
  }

  /* ---------- Tabla dinámica de filas ---------- */
  /* Uso: MF.tablaDinamica({ cuerpo: '#tbody', plantilla: fn(i), alCambiar: fn }) */
  MF.tablaDinamica = function (opciones) {
    const cuerpo = typeof opciones.cuerpo === 'string' ? document.querySelector(opciones.cuerpo) : opciones.cuerpo;
    if (!cuerpo) return null;

    const api = {
      cuerpo: cuerpo,
      filas() { return Array.from(cuerpo.querySelectorAll('tr')); },
      renumerar() {
        api.filas().forEach((tr, i) => {
          const n = tr.querySelector('[data-indice]');
          if (n) n.textContent = i + 1;
        });
        if (opciones.alCambiar) opciones.alCambiar(api);
      },
      agregar(datos) {
        const tr = document.createElement('tr');
        tr.innerHTML = opciones.plantilla(api.filas().length, datos || {});
        cuerpo.appendChild(tr);
        api.renumerar();
        return tr;
      },
      quitar(tr) {
        if (api.filas().length <= (opciones.minimo || 1)) {
          MF.aviso('Debe quedar al menos ' + (opciones.minimo || 1) + ' fila.', 'warning');
          return;
        }
        tr.remove();
        api.renumerar();
      },
      cargar(lista) {
        cuerpo.innerHTML = '';
        (lista || []).forEach((d) => {
          const tr = document.createElement('tr');
          tr.innerHTML = opciones.plantilla(api.filas().length, d);
          cuerpo.appendChild(tr);
        });
        api.renumerar();
      }
    };

    cuerpo.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-accion="quitar-fila"]');
      if (btn) { e.preventDefault(); api.quitar(btn.closest('tr')); }
    });
    cuerpo.addEventListener('input', () => { if (opciones.alCambiar) opciones.alCambiar(api); });

    // Pegar desde Excel: distribuye filas/columnas automáticamente
    cuerpo.addEventListener('paste', (e) => {
      const texto = (e.clipboardData || global.clipboardData).getData('text');
      if (!texto || texto.indexOf('\n') === -1 && texto.indexOf('\t') === -1) return;
      e.preventDefault();
      const celdaOrigen = e.target.closest('td');
      if (!celdaOrigen) return;
      const filaOrigen = celdaOrigen.parentElement;
      const idxFila = api.filas().indexOf(filaOrigen);
      const idxCol = Array.from(filaOrigen.children).indexOf(celdaOrigen);

      const matriz = texto.trim().split(/\r?\n/).map((l) => l.split(/\t|;/));
      matriz.forEach((cols, i) => {
        let tr = api.filas()[idxFila + i];
        if (!tr) tr = api.agregar();
        cols.forEach((val, j) => {
          const td = tr.children[idxCol + j];
          if (!td) return;
          const input = td.querySelector('input');
          if (input) input.value = String(val).trim().replace(',', '.');
        });
      });
      api.renumerar();
      MF.aviso(matriz.length + ' filas pegadas desde el portapapeles.', 'success');
    });

    return api;
  };

  /* ---------- Arranque ---------- */
  function iniciar() {
    MF.tema.aplicar(LS.get('tema', 'claro'));
    iniciarSidebar();
    marcarActivo();

    const btnTema = document.getElementById('mf-btn-tema');
    if (btnTema) btnTema.addEventListener('click', () => MF.tema.alternar());

    const btnImprimir = document.getElementById('mf-btn-imprimir');
    if (btnImprimir) btnImprimir.addEventListener('click', () => MF.imprimir());

    MF.graficos.autoIniciar();
    MF.marcarEsquemasDesplazables();

    let temporizadorAncho = null;
    global.addEventListener('resize', () => {
      MF.marcarEsquemasDesplazables();
      clearTimeout(temporizadorAncho);
      temporizadorAncho = setTimeout(() => MF.graficos.retematizarTodos(), 250);
    });

    // Validación en vivo genérica
    document.addEventListener('blur', (e) => {
      if (e.target.matches && e.target.matches('input[type="number"]')) MF.validarCampo(e.target);
    }, true);

    // Botones utilitarios declarativos
    document.addEventListener('click', (e) => {
      const exp = e.target.closest('[data-exportar]');
      if (exp) { e.preventDefault(); MF.exportarCSV(exp.getAttribute('data-exportar'), exp.getAttribute('data-nombre')); }
      const cop = e.target.closest('[data-copiar]');
      if (cop) { e.preventDefault(); MF.copiar(cop.getAttribute('data-copiar')); }
      const imp = e.target.closest('[data-imprimir]');
      if (imp) { e.preventDefault(); MF.imprimir(); }
    });

    // Cálculo sin recarga en los formularios marcados
    document.querySelectorAll('form[data-ajax]').forEach((f) => MF.formAjax(f));

    // Indicador de carga al enviar formularios clásicos
    document.querySelectorAll('form[data-cargando]:not([data-ajax])').forEach((f) => {
      f.addEventListener('submit', () => {
        const b = f.querySelector('[type="submit"]');
        if (b) {
          b.disabled = true;
          b.dataset.txt = b.innerHTML;
          b.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Calculando…';
        }
      });
    });

    // Tras una recarga con resultados, llevar la vista hasta ellos.
    // En la primera carga (formulario vacío) no se desplaza nada.
    const res = document.getElementById('mf-resultados');
    if (res && res.querySelector('[data-hay-resultados], [data-error-calculo]')) {
      setTimeout(() => res.scrollIntoView({ behavior: 'smooth', block: 'start' }), 250);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();

  global.MF = MF;
})(window);
