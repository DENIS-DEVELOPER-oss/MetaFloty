/* ============================================================
   MetaFlotPy · Conversores de unidades
   Las tarjetas se generan a partir de la tabla de magnitudes:
   agregar una unidad nueva es añadir una línea a este archivo.
   ============================================================ */
(function () {
  'use strict';

  // Factor = cuántas unidades base equivale 1 unidad de la fila
  const MAGNITUDES = [
    {
      clave: 'masa', titulo: 'Masa', icono: 'bi-box-seam', base: 'kg',
      unidades: [
        ['kg', 'Kilogramo (kg)', 1],
        ['g', 'Gramo (g)', 0.001],
        ['t', 'Tonelada métrica (t)', 1000],
        ['lb', 'Libra (lb)', 0.45359237],
        ['st', 'Tonelada corta (short ton)', 907.18474],
        ['lt', 'Tonelada larga (long ton)', 1016.0469],
        ['oz_t', 'Onza troy (oz t)', 0.0311035]
      ]
    },
    {
      clave: 'longitud', titulo: 'Longitud y tamaño de partícula', icono: 'bi-rulers', base: 'm',
      unidades: [
        ['m', 'Metro (m)', 1],
        ['cm', 'Centímetro (cm)', 0.01],
        ['mm', 'Milímetro (mm)', 0.001],
        ['um', 'Micrómetro (µm)', 0.000001],
        ['in', 'Pulgada (in)', 0.0254],
        ['ft', 'Pie (ft)', 0.3048]
      ]
    },
    {
      clave: 'volumen', titulo: 'Volumen', icono: 'bi-database', base: 'm3',
      unidades: [
        ['m3', 'Metro cúbico (m³)', 1],
        ['L', 'Litro (L)', 0.001],
        ['gal_us', 'Galón US', 0.003785412],
        ['gal_uk', 'Galón imperial', 0.004546092],
        ['ft3', 'Pie cúbico (ft³)', 0.0283168],
        ['bbl', 'Barril (bbl)', 0.158987]
      ]
    },
    {
      clave: 'caudal', titulo: 'Caudal', icono: 'bi-water', base: 'm3h',
      unidades: [
        ['m3h', 'Metro cúbico por hora (m³/h)', 1],
        ['Ls', 'Litro por segundo (L/s)', 3.6],
        ['Lmin', 'Litro por minuto (L/min)', 0.06],
        ['gpm', 'Galón US por minuto (gpm)', 0.2271247],
        ['m3d', 'Metro cúbico por día (m³/d)', 1 / 24]
      ]
    },
    {
      clave: 'presion', titulo: 'Presión', icono: 'bi-speedometer2', base: 'kPa',
      unidades: [
        ['kPa', 'Kilopascal (kPa)', 1],
        ['Pa', 'Pascal (Pa)', 0.001],
        ['bar', 'Bar', 100],
        ['psi', 'Libra por pulgada cuadrada (psi)', 6.894757],
        ['atm', 'Atmósfera (atm)', 101.325],
        ['mH2O', 'Metro de columna de agua', 9.80665]
      ]
    },
    {
      clave: 'potencia', titulo: 'Potencia y energía específica', icono: 'bi-lightning-charge', base: 'kW',
      unidades: [
        ['kW', 'Kilovatio (kW)', 1],
        ['W', 'Vatio (W)', 0.001],
        ['MW', 'Megavatio (MW)', 1000],
        ['hp', 'Caballo de fuerza (hp)', 0.7456999],
        ['CV', 'Caballo de vapor (CV)', 0.7354988]
      ]
    }
  ];

  const $ = (id) => document.getElementById(id);

  function tarjeta(m) {
    const opciones = m.unidades
      .filter((u) => u[2] !== null)
      .map((u) => '<option value="' + u[0] + '">' + u[1] + '</option>').join('');

    return '' +
      '<div class="mf-card" data-magnitud="' + m.clave + '">' +
        '<div class="mf-card__head">' +
          '<h3><i class="bi ' + m.icono + '"></i> ' + m.titulo + '</h3>' +
          '<span class="mf-badge ms-auto mf-no-print">En vivo</span>' +
        '</div>' +
        '<div class="mf-card__body">' +
          '<div class="row g-2 align-items-end mb-3">' +
            '<div class="col-12 col-lg-4">' +
              '<label class="form-label" for="' + m.clave + '-valor">Valor</label>' +
              '<input type="number" class="form-control text-end" id="' + m.clave + '-valor" step="any" placeholder="1">' +
            '</div>' +
            '<div class="col-6 col-lg-4">' +
              '<label class="form-label" for="' + m.clave + '-de">De</label>' +
              '<select class="form-select" id="' + m.clave + '-de">' + opciones + '</select>' +
            '</div>' +
            '<div class="col-6 col-lg-4">' +
              '<label class="form-label" for="' + m.clave + '-a">A</label>' +
              '<select class="form-select" id="' + m.clave + '-a">' + opciones + '</select>' +
            '</div>' +
          '</div>' +

          '<div class="mf-alerta mf-alerta-info mb-3">' +
            '<i class="bi bi-arrow-right-circle-fill"></i>' +
            '<div><strong id="' + m.clave + '-resultado">Ingresa un valor</strong></div>' +
          '</div>' +

          '<div class="mf-tabla-wrap">' +
            '<table class="mf-tabla" id="mf-tabla-' + m.clave + '">' +
              '<thead><tr><th class="mf-col-txt">Unidad</th><th>Equivalencia</th></tr></thead>' +
              '<tbody id="' + m.clave + '-tabla"></tbody>' +
            '</table>' +
          '</div>' +

          '<div class="d-flex gap-2 mt-3 mf-no-print">' +
            '<button class="btn btn-sm btn-mf-suave" data-exportar="#mf-tabla-' + m.clave + '" ' +
                    'data-nombre="conversion-' + m.clave + '"><i class="bi bi-filetype-csv"></i> Exportar</button>' +
            '<button class="btn btn-sm btn-mf-suave" data-invertir="' + m.clave + '">' +
              '<i class="bi bi-arrow-left-right"></i> Invertir</button>' +
          '</div>' +
        '</div>' +
      '</div>';
  }

  function convertir(m) {
    const valor = MF.num($(m.clave + '-valor').value, NaN);
    const de = $(m.clave + '-de').value;
    const a = $(m.clave + '-a').value;
    const buscar = (c) => m.unidades.find((u) => u[0] === c);
    const uDe = buscar(de), uA = buscar(a);
    const cuerpo = $(m.clave + '-tabla');

    if (isNaN(valor) || !uDe || !uA) {
      $(m.clave + '-resultado').textContent = 'Ingresa un valor numérico';
      cuerpo.innerHTML = '';
      return;
    }

    const enBase = valor * uDe[2];
    const resultado = enBase / uA[2];

    $(m.clave + '-resultado').textContent =
      MF.fmtAuto(valor) + ' ' + uDe[1].replace(/\s*\(.*\)/, '') +
      '  =  ' + MF.fmtAuto(resultado) + ' ' + uA[1].replace(/\s*\(.*\)/, '');

    cuerpo.innerHTML = m.unidades
      .filter((u) => u[2] !== null)
      .map((u) => '<tr><td class="mf-col-txt">' + u[1] + '</td><td>' +
                  MF.fmtAuto(enBase / u[2]) + '</td></tr>')
      .join('');
  }

  document.addEventListener('DOMContentLoaded', function () {
    const cont = $('mf-conversores');
    if (!cont) return;
    cont.innerHTML = MAGNITUDES.map(tarjeta).join('');

    MAGNITUDES.forEach(function (m) {
      const disponibles = m.unidades.filter((u) => u[2] !== null);
      $(m.clave + '-de').value = disponibles[0][0];
      $(m.clave + '-a').value = disponibles[Math.min(1, disponibles.length - 1)][0];
      $(m.clave + '-valor').value = 1;

      const refrescar = () => convertir(m);
      [m.clave + '-valor', m.clave + '-de', m.clave + '-a'].forEach(function (id) {
        $(id).addEventListener('input', refrescar);
        $(id).addEventListener('change', refrescar);
      });
      refrescar();
    });

    cont.addEventListener('click', function (e) {
      const btn = e.target.closest('[data-invertir]');
      if (!btn) return;
      const clave = btn.getAttribute('data-invertir');
      const m = MAGNITUDES.find((x) => x.clave === clave);
      const de = $(clave + '-de'), a = $(clave + '-a');
      const tmp = de.value; de.value = a.value; a.value = tmp;
      convertir(m);
    });

    /* ---- Temperatura ---- */
    let ocupado = false;
    document.querySelectorAll('[data-temp]').forEach(function (input) {
      input.addEventListener('input', function () {
        if (ocupado) return;
        const v = MF.num(input.value, NaN);
        if (isNaN(v)) return;
        const cual = input.getAttribute('data-temp');
        let c;
        if (cual === 'c') c = v;
        else if (cual === 'f') c = (v - 32) * 5 / 9;
        else c = v - 273.15;

        ocupado = true;
        const escribir = (id, valor) => {
          const e = $(id);
          if (e && e !== input) e.value = Number(valor.toFixed(2));
        };
        escribir('temp-c', c);
        escribir('temp-f', c * 9 / 5 + 32);
        escribir('temp-k', c + 273.15);
        ocupado = false;
      });
    });
  });
})();
