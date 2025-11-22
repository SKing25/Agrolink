// Lógica de la tabla general y gateway IP
(function(){
  const statusDiv = document.getElementById('status');
  const ipEl = document.getElementById('gatewayIP');
  const totalEl = document.getElementById('total');
  const socket = io(window.location.origin, { transports: ['polling'] });

  socket.on('connect', () => {
    if(statusDiv){
      statusDiv.textContent = 'Conectado al servidor WebSocket';
      statusDiv.style.background = '#d1e7dd';
      statusDiv.style.color = '#0f5132';
    }
  });

  socket.on('datos_iniciales', (payload) => {
    if (payload && payload.gateway_ip !== undefined && ipEl) {
      ipEl.textContent = payload.gateway_ip || '—';
    }
  });

  socket.on('gateway_ip', (data) => {
    if (ipEl && data && 'ip' in data) {
      ipEl.textContent = data.ip || '—';
    }
  });

  socket.on('connect_error', (err) => {
    if(statusDiv){
      statusDiv.textContent = 'Error de conexión: ' + (err && err.message ? err.message : err);
      statusDiv.style.background = '#f8d7da';
      statusDiv.style.color = '#721c24';
    }
  });
  socket.on('disconnect', (reason) => {
    if(statusDiv){
      statusDiv.textContent = 'Desconectado: ' + reason;
      statusDiv.style.background = '#fff3cd';
      statusDiv.style.color = '#856404';
    }
  });
  socket.on('reconnect_attempt', () => { if(statusDiv) statusDiv.textContent='Intentando reconectar...'; });
  socket.on('reconnect', () => { if(statusDiv) statusDiv.textContent='Reconectado'; });

  socket.on('nuevo_dato', (dato) => { agregarFila(dato, true); });

  function agregarFila(dato, alFrente){
    if(!dato) return;
    const tbody = document.querySelector('#tabla-datos tbody');
    if(!tbody) return;
    const fila = alFrente ? tbody.insertRow(0) : tbody.insertRow(-1);
    fila.className='nuevo';
    fila.insertCell(-1).textContent = dato.id ?? '-';
    fila.insertCell(-1).textContent = dato.nodeId ?? '-';
    fila.insertCell(-1).textContent = dato.temperatura!=null ? Number(dato.temperatura).toFixed(1) : '-';
    fila.insertCell(-1).textContent = dato.humedad!=null ? Number(dato.humedad).toFixed(1) : '-';
    fila.insertCell(-1).textContent = dato.soil_moisture!=null ? Number(dato.soil_moisture).toFixed(0) : '-';
    let luz='-';
    if(dato.light!=null && dato.percentage!=null) luz=`${Number(dato.light).toFixed(2)} - ${Number(dato.percentage).toFixed(0)}%`;
    else if(dato.light!=null) luz=Number(dato.light).toFixed(2);
    else if(dato.percentage!=null) luz=`${Number(dato.percentage).toFixed(0)}%`;
    fila.insertCell(-1).textContent = luz;
    fila.insertCell(-1).textContent = dato.fecha_creacion ?? '-';
    if(alFrente && totalEl){
      const m = totalEl.textContent.match(/\d+/);
      const current = m?parseInt(m[0]):0;
      totalEl.textContent = 'Total de registros: ' + (current+1);
    }
    while(tbody.rows.length>100) tbody.deleteRow(tbody.rows.length-1);
  }
})();

