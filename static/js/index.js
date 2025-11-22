// Lógica de la página principal (gateway IP)
(function(){
  const ipEl = document.getElementById('gatewayIP');
  const socket = io(window.location.origin, { transports: ['polling'] });
  socket.on('datos_iniciales', payload => {
    if(payload && ipEl && payload.gateway_ip!==undefined){ ipEl.textContent = payload.gateway_ip || '—'; }
  });
  socket.on('gateway_ip', data => { if(ipEl && data && 'ip' in data){ ipEl.textContent = data.ip || '—'; } });
})();

