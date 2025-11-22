// Lógica de página de nodo (mapa + gráficos + tabla)
(function(){
  if(!window.PAGE_DATA){ console.warn('PAGE_DATA no definido'); return; }
  const {
    thisNodeId, ubicacionInicial, ubicacionesTodos, centroLat, centroLon,
    camposNode, initialData, nodosList
  } = window.PAGE_DATA;

  // ========== MAPA LEAFLET ==========
  let map=null, layerControl=null;
  const grupos={}, markersByNode={};
  const colorCycle=['red','blue','green','orange','violet','grey','black','gold'];
  const colorsByNode={};
  (Array.isArray(nodosList)?nodosList:[]).concat(thisNodeId).forEach((nid,idx)=>{ if(nid && !colorsByNode[nid]) colorsByNode[nid]=colorCycle[idx%colorCycle.length]; });
  function getColor(nid){ return colorsByNode[nid] || colorCycle[0]; }
  function coloredIcon(color){
    const base='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/';
    return L.icon({
      iconUrl: base+`marker-icon-${color}.png`,
      shadowUrl: base+'marker-shadow.png',
      iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowSize:[41,41]
    });
  }
  function crearGrupoNodo(nid){ const lg=L.layerGroup(); grupos[nid]=lg; if(layerControl) layerControl.addOverlay(lg,'Nodo '+nid); return lg; }
  function ensureGrupo(nid){ return grupos[nid]||crearGrupoNodo(nid); }

  function initMap(){
    if(!window.L){ console.error('Leaflet no cargado'); return; }
    map=L.map('leaflet-map').setView([centroLat||0, centroLon||0], 18);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19, attribution:'&copy; OpenStreetMap'}).addTo(map);
    layerControl=L.control.layers(null,null,{collapsed:true}).addTo(map);
    setTimeout(()=>{ try{ map.invalidateSize(); }catch(e){} },100);
    Object.keys(ubicacionesTodos||{}).forEach(nid=>{
      const g=ensureGrupo(nid);
      const loc=ubicacionesTodos[nid];
      if(loc && loc.lat!=null && loc.lon!=null && nid!==thisNodeId){
        const m=L.marker([loc.lat,loc.lon],{icon:coloredIcon(getColor(nid))})
          .bindPopup('Nodo '+nid+'<br>lat: '+Number(loc.lat).toFixed(6)+'<br>lon: '+Number(loc.lon).toFixed(6));
        m.addTo(g); markersByNode[nid]=m;
      }
      if(nid===thisNodeId) g.addTo(map);
    });
    if(ubicacionInicial && ubicacionInicial.lat && ubicacionInicial.lon){
      actualizarUbicacionNodoGeneric(thisNodeId, ubicacionInicial.lat, ubicacionInicial.lon, true);
    }
  }

  function actualizarUbicacionNodoGeneric(nid, lat, lon, pan){
    if(!map || lat==null || lon==null) return;
    const g=ensureGrupo(nid);
    if(markersByNode[nid]){ markersByNode[nid].setLatLng([lat,lon]); }
    else {
      const m=L.marker([lat,lon],{icon:coloredIcon(getColor(nid))})
        .bindPopup('Nodo '+nid+'<br>lat: '+Number(lat).toFixed(6)+'<br>lon: '+Number(lon).toFixed(6));
      m.addTo(g); markersByNode[nid]=m;
    }
    if(pan){ try{ map.panTo([lat,lon]); }catch(e){} }
  }

  // ========== SOCKET + TABLA + GRÁFICAS ==========
  const socket=io(window.location.origin,{transports:['polling']});
  const ubicacionEl=document.getElementById('ubicacionNodo');
  const statusDiv=document.getElementById('status');
  socket.on('connect',()=>{ if(statusDiv){ statusDiv.textContent='Conectado al servidor WebSocket'; statusDiv.style.background='#d1e7dd'; statusDiv.style.color='#0f5132'; } });
  socket.on('ubicacion_nodo', data=>{
    if(!data || !data.nodeId) return;
    const nid=String(data.nodeId); const lat=Number(data.lat); const lon=Number(data.lon);
    const isCurrent=nid===thisNodeId;
    actualizarUbicacionNodoGeneric(nid, lat, lon, isCurrent);
    if(isCurrent && ubicacionEl && !Number.isNaN(lat) && !Number.isNaN(lon)){
      ubicacionEl.textContent=`lat: ${lat.toFixed(6)}, lon: ${lon.toFixed(6)}`;
    }
  });

  function clampLen(arr,max=200){ while(arr.length>max) arr.shift(); }
  function pushIfDefined(arr,v){ arr.push((v==null)?null:Number(v)); }

  // Preparar datos para gráficas
  const sorted = Array.isArray(initialData) ? [...initialData].sort((a,b)=>{
    const ta=a.timestamp || (a.fecha_creacion? Date.parse(a.fecha_creacion)/1000:0);
    const tb=b.timestamp || (b.fecha_creacion? Date.parse(b.fecha_creacion)/1000:0);
    return ta-tb;
  }) : [];
  const labels = sorted.map(d=> d.fecha_creacion || (d.timestamp? new Date(d.timestamp*1000).toISOString():'') );

  let chartTemperatura, chartHumedad, chartSoil, chartLight;
  try{
    if(camposNode.temperatura){
      const dataTemp = sorted.map(d=> d.temperatura!=null? Number(d.temperatura): null);
      chartTemperatura = new Chart(document.getElementById('chartTemperatura'),{type:'line',data:{labels:[...labels],datasets:[{label:'°C',data:dataTemp,borderColor:'#ef4444',tension:0.2,spanGaps:true}]},options:{responsive:true,maintainAspectRatio:false}});
    }
    if(camposNode.humedad){
      const dataHum = sorted.map(d=> d.humedad!=null? Number(d.humedad): null);
      chartHumedad = new Chart(document.getElementById('chartHumedad'),{type:'line',data:{labels:[...labels],datasets:[{label:'%',data:dataHum,borderColor:'#3b82f6',tension:0.2,spanGaps:true}]},options:{responsive:true,maintainAspectRatio:false}});
    }
    if(camposNode.soil_moisture){
      const dataSoil = sorted.map(d=> d.soil_moisture!=null? Number(d.soil_moisture): null);
      chartSoil = new Chart(document.getElementById('chartSoilMoisture'),{type:'line',data:{labels:[...labels],datasets:[{label:'Soil',data:dataSoil,borderColor:'#10b981',tension:0.2,spanGaps:true}]},options:{responsive:true,maintainAspectRatio:false}});
    }
    if(camposNode.light || camposNode.percentage){
      const dataLight = sorted.map(d=> d.light!=null? Number(d.light): null);
      const dataPct = sorted.map(d=> d.percentage!=null? Number(d.percentage): null);
      chartLight = new Chart(document.getElementById('chartLight'),{type:'line',data:{labels:[...labels],datasets:[{label:'Luz (lux)',data:dataLight,borderColor:'#f59e0b',tension:0.2,spanGaps:true},{label:'Luz (%)',data:dataPct,borderColor:'#8b5cf6',tension:0.2,spanGaps:true}]},options:{responsive:true,maintainAspectRatio:false}});
    }
  }catch(e){ console.error('Error creando gráficas:',e); }

  socket.on('nuevo_dato', dato => {
    if(!dato || dato.nodeId !== thisNodeId) return;
    insertarFila(dato);
    const label = dato.fecha_creacion || (dato.timestamp? new Date(dato.timestamp*1000).toISOString(): '');
    if(chartTemperatura){ chartTemperatura.data.labels.push(label); clampLen(chartTemperatura.data.labels); pushIfDefined(chartTemperatura.data.datasets[0].data,dato.temperatura); clampLen(chartTemperatura.data.datasets[0].data); chartTemperatura.update('none'); }
    if(chartHumedad){ chartHumedad.data.labels.push(label); clampLen(chartHumedad.data.labels); pushIfDefined(chartHumedad.data.datasets[0].data,dato.humedad); clampLen(chartHumedad.data.datasets[0].data); chartHumedad.update('none'); }
    if(chartSoil){ chartSoil.data.labels.push(label); clampLen(chartSoil.data.labels); pushIfDefined(chartSoil.data.datasets[0].data,dato.soil_moisture); clampLen(chartSoil.data.datasets[0].data); chartSoil.update('none'); }
    if(chartLight){ chartLight.data.labels.push(label); clampLen(chartLight.data.labels); pushIfDefined(chartLight.data.datasets[0].data,dato.light); pushIfDefined(chartLight.data.datasets[1].data,dato.percentage); clampLen(chartLight.data.datasets[0].data); clampLen(chartLight.data.datasets[1].data); chartLight.update('none'); }
  });

  function insertarFila(d){
    if(!d) return;
    const tbody=document.querySelector('#tabla-datos tbody');
    if(!tbody) return;
    if(d.id!==undefined){
      for(let i=0;i<tbody.rows.length;i++){
        const c=tbody.rows[i].cells[0];
        if(c && c.textContent==d.id) return;
      }
    }
    const fila=tbody.insertRow(0); fila.className='nuevo';
    fila.insertCell(-1).textContent=d.id ?? '-';
    if(camposNode.temperatura) fila.insertCell(-1).textContent=d.temperatura!=null? Number(d.temperatura).toFixed(1):'-';
    if(camposNode.humedad) fila.insertCell(-1).textContent=d.humedad!=null? Number(d.humedad).toFixed(1):'-';
    if(camposNode.soil_moisture) fila.insertCell(-1).textContent=d.soil_moisture!=null? Number(d.soil_moisture).toFixed(0):'-';
    if(camposNode.light || camposNode.percentage){
      let luz='-';
      if(d.light!=null && d.percentage!=null) luz=`${Number(d.light).toFixed(2)} - ${Number(d.percentage).toFixed(0)}%`;
      else if(d.light!=null) luz=Number(d.light).toFixed(2);
      else if(d.percentage!=null) luz=`${Number(d.percentage).toFixed(0)}%`;
      fila.insertCell(-1).textContent=luz;
    }
    fila.insertCell(-1).textContent=d.timestamp ?? '-';
    fila.insertCell(-1).textContent=d.fecha_creacion ?? '-';
    const totalEl=document.getElementById('total');
    if(totalEl){ const m=totalEl.textContent.match(/\d+/); const current=m?parseInt(m[0]):0; totalEl.textContent='Total de registros: '+(current+1); }
    while(tbody.rows.length>100) tbody.deleteRow(tbody.rows.length-1);
  }

  // Inicializar mapa
  initMap();
})();

