/* ============================================================
   MetaFlotPy · Módulo I — Entrada dinámica de tamizado
   Tabla de mallas editable con series ASTM/Tyler, verificación
   de masa en vivo y vista previa de la curva granulométrica.
   ============================================================ */
(function (global) {
  'use strict';

  const MFT = {};

  function plantillaFila(i, d) {
    d = d || {};
    const nombre = d.nombre !== undefined ? d.nombre : '';
    const abertura = d.abertura !== undefined ? d.abertura : '';
    const peso = d.peso !== undefined ? d.peso : '';
    return '' +
      '<td class="mf-col-txt"><span class="mf-faint mf-num" data-indice>' + (i + 1) + '</span></td>' +
      '<td class="mf-col-txt"><input type="text" class="form-control form-control-sm" name="nombre_malla[]" ' +
        'value="' + String(nombre).replace(/"/g, '&quot;') + '" placeholder="N.º 100" autocomplete="off"></td>' +
      '<td><input type="number" class="form-control form-control-sm text-end" name="abertura[]" ' +
        'value="' + abertura + '" step="0.001" min="0.001" placeholder="0,150" required></td>' +
      '<td><input type="number" class="form-control form-control-sm text-end" name="peso_retenido[]" ' +
        'value="' + peso + '" step="0.01" min="0" placeholder="0,00"></td>' +
      '<td><span class="mf-num mf-muted" data-pct>—</span></td>' +
      '<td class="text-center">' +
        '<button type="button" class="btn btn-sm btn-mf-suave" data-accion="quitar-fila" title="Eliminar fila">' +
          '<i class="bi bi-trash3"></i></button></td>';
  }

  MFT.iniciar = function (opciones) {
    opciones = opciones || {};
    const form = document.getElementById('mf-form-tamizado');
    if (!form) return;

    const inputPeso = document.getElementById('peso_total');
    const resumenMasa = document.getElementById('mf-resumen-masa');
    const totalPeso = document.getElementById('mf-total-peso');
    const totalPct = document.getElementById('mf-total-pct');
    const vistaPrevia = document.getElementById('mf-vista-previa');

    const tabla = MF.tablaDinamica({
      cuerpo: '#mf-mallas',
      plantilla: plantillaFila,
      minimo: 3,
      alCambiar: actualizar
    });

    /* ----- Verificación de masa y porcentajes en vivo ----- */
    function actualizar() {
      const filas = tabla.filas();
      let suma = 0;
      filas.forEach((tr) => {
        const p = MF.num(tr.querySelector('[name="peso_retenido[]"]').value, 0);
        suma += p;
      });

      const declarado = MF.num(inputPeso ? inputPeso.value : 0, 0);
      const base = declarado > 0 ? declarado : suma;

      let acum = 0;
      filas.forEach((tr) => {
        const p = MF.num(tr.querySelector('[name="peso_retenido[]"]').value, 0);
        const celda = tr.querySelector('[data-pct]');
        if (base > 0 && p > 0) {
          acum += p;
          celda.textContent = MF.fmt(p / base * 100, 2) + ' %';
          celda.classList.remove('mf-muted');
        } else {
          celda.textContent = '—';
          celda.classList.add('mf-muted');
        }
      });

      if (totalPeso) totalPeso.textContent = MF.fmt(suma, 2);
      if (totalPct) totalPct.textContent = base > 0 ? MF.fmt(suma / base * 100, 2) + ' %' : '—';

      if (resumenMasa) {
        if (declarado <= 0) {
          resumenMasa.className = 'mf-badge';
          resumenMasa.innerHTML = '<i class="bi bi-info-circle"></i> Se usará la suma de retenidos como masa total';
        } else {
          const dif = Math.abs(declarado - suma);
          const difPct = declarado > 0 ? dif / declarado * 100 : 0;
          if (difPct <= 1) {
            resumenMasa.className = 'mf-badge mf-badge-success';
            resumenMasa.innerHTML = '<i class="bi bi-check-circle"></i> Masa cuadrada (desviación ' + MF.fmt(difPct, 2) + ' %)';
          } else if (difPct <= 3) {
            resumenMasa.className = 'mf-badge mf-badge-warning';
            resumenMasa.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Desviación ' + MF.fmt(difPct, 2) + ' % — revisa el pesaje';
          } else {
            resumenMasa.className = 'mf-badge mf-badge-danger';
            resumenMasa.innerHTML = '<i class="bi bi-x-octagon"></i> Desviación ' + MF.fmt(difPct, 2) + ' % — fuera de tolerancia';
          }
        }
      }

      dibujarVistaPrevia(base);
    }

    /* ----- Vista previa de la curva mientras se escribe ----- */
    let temporizador = null;
    function dibujarVistaPrevia(base) {
      if (!vistaPrevia || !global.Plotly) return;
      clearTimeout(temporizador);
      temporizador = setTimeout(() => {
        const datos = [];
        tabla.filas().forEach((tr) => {
          const a = MF.num(tr.querySelector('[name="abertura[]"]').value, NaN);
          const p = MF.num(tr.querySelector('[name="peso_retenido[]"]').value, NaN);
          if (!isNaN(a) && a > 0 && !isNaN(p) && p >= 0) datos.push({ a: a, p: p });
        });
        if (datos.length < 2 || base <= 0) {
          vistaPrevia.innerHTML = '<div class="mf-vacio"><i class="bi bi-activity"></i>' +
            '<p>Completa al menos dos mallas con peso para ver la curva preliminar.</p></div>';
          return;
        }
        datos.sort((x, y) => y.a - x.a);
        let acum = 0;
        const x = [], yPas = [], yRet = [];
        datos.forEach((d) => {
          acum += d.p / base * 100;
          x.push(d.a);
          yRet.push(acum);
          yPas.push(Math.max(0, 100 - acum));
        });

        const fig = {
          data: [
            { x: x, y: yPas, mode: 'markers+lines', name: '% Pasante', line: { width: 2.5 }, marker: { size: 7 } },
            { x: x, y: yRet, mode: 'markers+lines', name: '% Retenido acum.', line: { width: 2, dash: 'dot' }, marker: { size: 6 } }
          ],
          layout: {
            margin: { l: 62, r: 24, t: 20, b: 56 },
            xaxis: { title: 'Abertura d (mm)', type: 'log' },
            yaxis: { title: 'Porcentaje (%)', range: [0, 102] },
            hovermode: 'x unified'
          }
        };
        MF.graficos.dibujar(vistaPrevia, fig);
      }, 250);
    }

    /* ----- Barra de herramientas ----- */
    function cargarSerie(serie, conPesos) {
      const filas = serie.map((m) => ({
        nombre: m[0],
        abertura: m[1],
        peso: conPesos ? m[2] : ''
      }));
      tabla.cargar(filas);
      MF.aviso(filas.length + ' mallas cargadas.', 'success');
    }

    document.querySelectorAll('[data-serie]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const clave = btn.getAttribute('data-serie');
        const serie = opciones[clave];
        if (!serie) { MF.aviso('Serie no disponible.', 'warning'); return; }
        cargarSerie(serie, false);
      });
    });

    const btnAgregar = document.getElementById('mf-agregar-malla');
    if (btnAgregar) btnAgregar.addEventListener('click', () => {
      const tr = tabla.agregar();
      const inp = tr.querySelector('[name="nombre_malla[]"]');
      if (inp) inp.focus();
    });

    const btnLimpiar = document.getElementById('mf-limpiar');
    if (btnLimpiar) btnLimpiar.addEventListener('click', () => {
      tabla.filas().forEach((tr) => {
        tr.querySelector('[name="peso_retenido[]"]').value = '';
      });
      if (inputPeso) inputPeso.value = '';
      actualizar();
      MF.aviso('Pesos borrados.', 'info');
    });

    const btnEjemplo = document.getElementById('mf-ejemplo');
    if (btnEjemplo) btnEjemplo.addEventListener('click', () => {
      if (inputPeso) inputPeso.value = '1000';
      tabla.cargar(opciones.ejemplo || []);
      actualizar();
      MF.aviso('Datos de ejemplo cargados. Pulsa «Calcular» para ver el análisis.', 'info', 5000);
    });

    if (inputPeso) inputPeso.addEventListener('input', actualizar);

    /* ----- Estado inicial ----- */
    if (!tabla.filas().length) {
      tabla.cargar((opciones.astm || []).slice(0, 10).map((m) => ({ nombre: m[0], abertura: m[1], peso: '' })));
    }
    actualizar();

    // Tras un cálculo AJAX, los gráficos nuevos se re-tematizan solos;
    // aquí solo refrescamos la vista previa por si cambió la masa base.
    MF.formAjax.alActualizar.push(() => actualizar());
  };

  global.MFTamizado = MFT;
})(window);
