/* ============================================================
   MetaFlotPy · Utilitarios metalúrgicos
   Todos los cálculos se recalculan en vivo mientras se escribe.
   ============================================================ */
(function () {
  'use strict';

  const OZ_TROY_G = 31.1035;
  const $ = (id) => document.getElementById(id);
  const val = (id, def) => MF.num($(id) ? $(id).value : '', def === undefined ? NaN : def);
  const set = (id, texto) => { const e = $(id); if (e) e.textContent = texto; };

  /* ---------------- Densidad de pulpa ---------------- */
  function densidadPulpa(pctSolidos, gs) {
    if (!(pctSolidos > 0 && pctSolidos < 100 && gs > 0)) return null;
    return 100 / (pctSolidos / gs + (100 - pctSolidos));
  }

  function calcularPulpa() {
    const s = val('pulpa-solidos', NaN);
    const gs = val('pulpa-gs', NaN);
    const rho = densidadPulpa(s, gs);

    if (rho === null) {
      ['pulpa-densidad', 'pulpa-densidad-kg', 'pulpa-cs', 'pulpa-sv', 'pulpa-dilucion', 'pulpa-agua']
        .forEach((id) => set(id, '—'));
      return;
    }

    const cs = rho * (s / 100) * 1000;          // g de sólido por litro de pulpa
    const sv = cs / (gs * 10);                  // % de sólidos en volumen
    const dilucion = (100 - s) / s;             // masa de agua por masa de sólido

    set('pulpa-densidad', MF.fmt(rho, 4));
    set('pulpa-densidad-kg', MF.fmt(rho * 1000, 1));
    set('pulpa-cs', MF.fmt(cs, 1));
    set('pulpa-sv', MF.fmt(sv, 2));
    set('pulpa-dilucion', MF.fmt(dilucion, 3) + ' : 1');
    set('pulpa-agua', MF.fmt(dilucion, 3));

    graficarPulpa(s, gs, rho);
  }

  let temporizador = null;
  function graficarPulpa(s, gs, rho) {
    const cont = $('mf-grafico-pulpa');
    if (!cont || !window.Plotly) return;
    clearTimeout(temporizador);
    temporizador = setTimeout(() => {
      const x = [], y = [];
      for (let p = 5; p <= 80; p += 1) {
        x.push(p);
        y.push(densidadPulpa(p, gs));
      }
      MF.graficos.dibujar(cont, {
        data: [
          { x: x, y: y, mode: 'lines', name: 'Gs = ' + MF.fmt(gs, 2), line: { width: 3 },
            hovertemplate: '%S = %{x:.0f} %<br>ρp = %{y:.4f} g/cm³<extra></extra>' },
          { x: [s], y: [rho], mode: 'markers+text', name: 'Punto actual',
            marker: { size: 13, symbol: 'diamond' }, text: ['actual'], textposition: 'top center' }
        ],
        layout: {
          title: 'Densidad de pulpa según el % de sólidos',
          xaxis: { title: '% de sólidos en peso' },
          yaxis: { title: 'Densidad de pulpa (g/cm³)' },
          margin: { l: 58, r: 18, t: 50, b: 52 },
          showlegend: false,
          hovermode: 'x unified'
        }
      });
    }, 180);
  }

  /* ---------------- Equivalencias de ley ---------------- */
  let actualizandoLey = false;
  function sincronizarLey(origen) {
    if (actualizandoLey) return;
    const campo = origen.getAttribute('data-ley');
    const v = MF.num(origen.value, NaN);
    if (isNaN(v)) return;

    let gt;                       // se normaliza todo a gramos por tonelada
    if (campo === 'pct') gt = v * 10000;
    else if (campo === 'gt' || campo === 'ppm') gt = v;
    else if (campo === 'ozt') gt = v * OZ_TROY_G;
    else return;

    actualizandoLey = true;
    const escribir = (id, valor, dec) => {
      const e = $(id);
      if (e && e !== origen) e.value = Number(valor.toFixed(dec));
    };
    escribir('ley-pct', gt / 10000, 6);
    escribir('ley-gt', gt, 4);
    escribir('ley-ppm', gt, 4);
    escribir('ley-ozt', gt / OZ_TROY_G, 6);
    actualizandoLey = false;
  }

  /* ---------------- Dosificación de reactivos ---------------- */
  function calcularReactivos() {
    const t = val('reac-tratamiento', NaN);
    const dosis = val('reac-dosis', NaN);
    const conc = val('reac-conc', NaN);

    if (!(t > 0 && dosis >= 0)) {
      ['reac-kg-h', 'reac-kg-dia', 'reac-t-mes', 'reac-l-h', 'reac-ml-min'].forEach((id) => set(id, '—'));
      return;
    }

    const kgH = t * dosis / 1000;
    set('reac-kg-h', MF.fmt(kgH, 3));
    set('reac-kg-dia', MF.fmt(kgH * 24, 2));
    set('reac-t-mes', MF.fmt(kgH * 24 * 30 / 1000, 3));

    if (conc > 0) {
      const litrosH = kgH * 100 / conc;         // solución al conc %, densidad ≈ 1 kg/L
      set('reac-l-h', MF.fmt(litrosH, 2));
      set('reac-ml-min', MF.fmt(litrosH * 1000 / 60, 1));
    } else {
      set('reac-l-h', '—');
      set('reac-ml-min', '—');
    }
  }

  /* ---------------- Tiempo de residencia ---------------- */
  function calcularResidencia() {
    const v = val('res-volumen', NaN);
    const q = val('res-caudal', NaN);
    const n = Math.max(1, Math.round(val('res-unidades', 1)));

    if (!(v > 0 && q > 0)) {
      ['res-unidad', 'res-total', 'res-volumen-total'].forEach((id) => set(id, '—'));
      return;
    }
    const tauMin = v / q * 60;
    set('res-unidad', MF.fmt(tauMin, 2) + ' min');
    set('res-total', MF.fmt(tauMin * n, 2) + ' min');
    set('res-volumen-total', MF.fmt(v * n, 1) + ' m³');
  }

  /* ---------------- Carga circulante por mallas ---------------- */
  function calcularCC() {
    const d = val('cc-d', NaN), o = val('cc-o', NaN), u = val('cc-u', NaN);
    const denom = d - u;
    if (isNaN(d) || isNaN(o) || isNaN(u) || Math.abs(denom) < 1e-9) {
      set('cc-resultado', '—');
      set('cc-nota', 'Los tres análisis deben ser distintos entre sí.');
      return;
    }
    const cc = (o - d) / denom * 100;
    set('cc-resultado', MF.fmt(cc, 1) + ' %');
    if (cc < 0) {
      set('cc-nota', 'Resultado negativo: revisa el orden de las muestras (el rebose debe ser el más fino).');
    } else {
      set('cc-nota', 'Por cada tonelada de producto se recirculan ' + MF.fmt(cc / 100, 2) + ' t.');
    }
  }

  /* ---------------- Enlaces ---------------- */
  function enlazar(ids, fn) {
    ids.forEach((id) => {
      const e = $(id);
      if (e) e.addEventListener('input', fn);
    });
    fn();
  }

  document.addEventListener('DOMContentLoaded', function () {
    enlazar(['pulpa-solidos', 'pulpa-gs'], calcularPulpa);
    enlazar(['reac-tratamiento', 'reac-dosis', 'reac-conc'], calcularReactivos);
    enlazar(['res-volumen', 'res-caudal', 'res-unidades'], calcularResidencia);
    enlazar(['cc-d', 'cc-o', 'cc-u'], calcularCC);

    document.querySelectorAll('[data-ley]').forEach((e) => {
      e.addEventListener('input', function () { sincronizarLey(e); });
    });
  });
})();
