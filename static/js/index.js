// Lógica de la página principal (gateway IP + mapa de nodos + promedios acumulados)
(function(){
  const ipEl = document.getElementById('gatewayIP');
  const socket = io(window.location.origin, { transports: ['polling'] });
  const pageData = window.PAGE_DATA || {};
  const ubicacionesTodos = pageData.ubicacionesTodos || {};
  let centroLat = pageData.centroLat || 0;
  let centroLon = pageData.centroLon || 0;
  const nodos = pageData.nodos || [];

  // Si centroLat/Lon son 0 y hay ubicaciones, tomar la primera
  if((!centroLat && !centroLon) && ubicacionesTodos && Object.keys(ubicacionesTodos).length){
    const first = ubicacionesTodos[Object.keys(ubicacionesTodos)[0]];
    if(first && first.lat!=null && first.lon!=null){ centroLat = first.lat; centroLon = first.lon; }
  }

  // Elementos UI
  const ultimoDatoHoraEl = document.querySelector('#metricUltimo .value.time-local');
  const ultimosTbody = document.getElementById('ultimosTbody');
  const avgTempEl = document.getElementById('avgTemp');
  const avgHumEl = document.getElementById('avgHum');
  const avgLightEl = document.getElementById('avgLight');
  const avgSoilEl = document.getElementById('avgSoil');

  // Acumuladores
  const seriesTemp = []; // números
  const seriesHum = [];
  const seriesLight = [];
  const seriesSoil = [];
  const labelsTemp = []; // timestamps para minigráficas (podemos compartir labels)
  const labelsHum = [];
  const labelsLight = [];
  const labelsSoil = [];

  function safePush(arr, v){ if(v!==undefined && v!==null && !Number.isNaN(Number(v))) arr.push(Number(v)); }
  function average(arr){ if(!arr.length) return null; let s=0; for(const n of arr) s+=n; return s/arr.length; }

  // ================= Tiempo local =================
  function toLocalTime(ts){
    if(!ts) return '—';
    let d = new Date(ts);
    if(isNaN(d.getTime())) { d = new Date(String(ts).replace(' ','T')); if(isNaN(d.getTime())) return ts; }
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  function refreshLocalTimes(){
    document.querySelectorAll('.time-local[data-ts]').forEach(el=>{
      const raw = el.getAttribute('data-ts');
      el.textContent = toLocalTime(raw);
    });
  }

  // ================= Mapa Leaflet =================
  let map = null;
  const markers = {}; // nodeId -> marker
  const colorCycle = ['red','blue','green','orange','violet','grey','black','gold'];
  const colorsByNode = {};
  (Array.isArray(nodos)?nodos:[]).forEach((nid,idx)=>{ colorsByNode[nid] = colorCycle[idx % colorCycle.length]; });
  function coloredIcon(color){
    const base='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/';
    return L.icon({
      iconUrl: base+`marker-icon-${color}.png`,
      shadowUrl: base+'marker-shadow.png',
      iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowSize:[41,41]
    });
  }
  function initMap(){
    const mapDiv = document.getElementById('index-map');
    if(!mapDiv || !window.L) return;
    map = L.map(mapDiv).setView([centroLat, centroLon], 17);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{ maxZoom:19, attribution:'&copy; OpenStreetMap' }).addTo(map);
    // Crear marcadores iniciales
    Object.keys(ubicacionesTodos).forEach(nid => {
      const loc = ubicacionesTodos[nid];
      if(!loc || loc.lat==null || loc.lon==null) return;
      const icon = coloredIcon(colorsByNode[nid] || 'red');
      const m = L.marker([loc.lat, loc.lon], { icon })
        .bindPopup('Nodo '+nid+'<br>lat: '+Number(loc.lat).toFixed(6)+'<br>lon: '+Number(loc.lon).toFixed(6));
      m.addTo(map);
      markers[nid] = m;
    });
    // Ajustar vista si hay varios nodos
    const ids = Object.keys(markers);
    if(ids.length>1){
      const group = L.featureGroup(ids.map(i=>markers[i]));
      try { map.fitBounds(group.getBounds().pad(0.15)); } catch(e) {}
    }
  }
  function updateMarker(nid, lat, lon){
    if(!map || lat==null || lon==null) return;
    if(markers[nid]){ markers[nid].setLatLng([lat,lon]); markers[nid].setPopupContent('Nodo '+nid+'<br>lat: '+lat.toFixed(6)+'<br>lon: '+lon.toFixed(6)); }
    else {
      const icon = coloredIcon(colorsByNode[nid] || 'red');
      markers[nid] = L.marker([lat, lon], { icon }).bindPopup('Nodo '+nid+'<br>lat: '+lat.toFixed(6)+'<br>lon: '+lon.toFixed(6)).addTo(map);
    }
  }

  // ================= Mini gráficas (sparklines) =================
  let sparkTemp=null, sparkHum=null, sparkLight=null, sparkSoil=null;
  function initSparklines(){
    if(!window.Chart) return;
    const baseOpts = { responsive:true, maintainAspectRatio:false, elements:{ point:{ radius:0 } }, plugins:{legend:{display:false}}, scales:{x:{display:false},y:{display:false}} };
    const makeConfig = (labels, data, color) => ({ type:'line', data:{ labels:[...labels], datasets:[{ data:[...data], borderColor:color, borderWidth:1.4, tension:0.25 }] }, options: baseOpts });
    sparkTemp = new Chart(document.getElementById('sparkTemp'), makeConfig(labelsTemp, seriesTemp, '#ef4444'));
    sparkHum  = new Chart(document.getElementById('sparkHum'),  makeConfig(labelsHum, seriesHum, '#3b82f6'));
    sparkLight= new Chart(document.getElementById('sparkLight'),makeConfig(labelsLight, seriesLight, '#f59e0b'));
    sparkSoil = new Chart(document.getElementById('sparkSoil'), makeConfig(labelsSoil, seriesSoil, '#10b981'));
  }
  function updateSparklines(){
    if(sparkTemp){ sparkTemp.data.labels=[...labelsTemp]; sparkTemp.data.datasets[0].data=[...seriesTemp]; sparkTemp.update('none'); }
    if(sparkHum){ sparkHum.data.labels=[...labelsHum]; sparkHum.data.datasets[0].data=[...seriesHum]; sparkHum.update('none'); }
    if(sparkLight){ sparkLight.data.labels=[...labelsLight]; sparkLight.data.datasets[0].data=[...seriesLight]; sparkLight.update('none'); }
    if(sparkSoil){ sparkSoil.data.labels=[...labelsSoil]; sparkSoil.data.datasets[0].data=[...seriesSoil]; sparkSoil.update('none'); }
  }
  function clamp(arr, max=150){ while(arr.length>max) arr.shift(); }

  function recalcAverages(){
    const aT = average(seriesTemp); avgTempEl && (avgTempEl.textContent = aT!=null ? aT.toFixed(1)+'°C':'—');
    const aH = average(seriesHum);  avgHumEl && (avgHumEl.textContent  = aH!=null ? aH.toFixed(1)+'%':'—');
    const aL = average(seriesLight);avgLightEl && (avgLightEl.textContent= aL!=null ? aL.toFixed(1):'—');
    const aS = average(seriesSoil); avgSoilEl && (avgSoilEl.textContent = aS!=null ? aS.toFixed(0):'—');
  }

  // ================= Socket =================
  socket.on('connect', () => { refreshLocalTimes(); });
  socket.on('datos_iniciales', (payload) => {
    if (payload && payload.gateway_ip !== undefined && ipEl) ipEl.textContent = payload.gateway_ip || '—';
    refreshLocalTimes();
  });
  socket.on('gateway_ip', (data) => { if (ipEl && data && 'ip' in data) ipEl.textContent = data.ip || '—'; });
  socket.on('ubicacion_nodo', data => {
    if(!data || !data.nodeId) return;
    const lat = Number(data.lat), lon = Number(data.lon);
    if(!Number.isNaN(lat) && !Number.isNaN(lon)) updateMarker(String(data.nodeId), lat, lon);
  });
  socket.on('nuevo_dato', dato => {
    if(!dato) return;
    // Actualizar hora último dato
    if(ultimoDatoHoraEl && dato.fecha_creacion){ ultimoDatoHoraEl.setAttribute('data-ts', dato.fecha_creacion); ultimoDatoHoraEl.textContent = toLocalTime(dato.fecha_creacion); }
    // Actualizar fila de tabla (reemplazar única fila)
    if(ultimosTbody){
      ultimosTbody.innerHTML = '';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${dato.id??'-'}</td>`+
        `<td>${dato.nodeId??'-'}</td>`+
        `<td>${dato.temperatura!=null?Number(dato.temperatura).toFixed(1):'-'}</td>`+
        `<td>${dato.humedad!=null?Number(dato.humedad).toFixed(1):'-'}</td>`+
        `<td>${dato.soil_moisture!=null?Number(dato.soil_moisture).toFixed(1):'-'}</td>`+
        `<td>${(dato.light!=null&&dato.percentage!=null)?`${Number(dato.light).toFixed(2)} - ${Number(dato.percentage).toFixed(0)}%`:(dato.light!=null?Number(dato.light).toFixed(2):(dato.percentage!=null?Number(dato.percentage).toFixed(0)+'%':'-'))}</td>`+
        `<td class="time-local" data-ts="${dato.fecha_creacion??''}">${dato.fecha_creacion?toLocalTime(dato.fecha_creacion):'-'}</td>`;
      ultimosTbody.appendChild(tr);
    }
    // Acumular para promedios globales (toma todos los datos de todos los nodos)
    safePush(seriesTemp, dato.temperatura); clamp(seriesTemp);
    safePush(seriesHum, dato.humedad); clamp(seriesHum);
    safePush(seriesLight, dato.light); clamp(seriesLight);
    safePush(seriesSoil, dato.soil_moisture); clamp(seriesSoil);
    // Labels (usar timestamp texto)
    const lbl = dato.fecha_creacion || (dato.timestamp? new Date(dato.timestamp*1000).toISOString(): Date.now());
    labelsTemp.push(lbl); clamp(labelsTemp);
    labelsHum.push(lbl); clamp(labelsHum);
    labelsLight.push(lbl); clamp(labelsLight);
    labelsSoil.push(lbl); clamp(labelsSoil);
    // Recalcular y refrescar sparklines
    recalcAverages(); updateSparklines();
  });

  // ================= Init =================
  function init(){ refreshLocalTimes(); initMap(); initSparklines(); recalcAverages(); }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', init); } else { init(); }
  setInterval(refreshLocalTimes, 60000);
})();
