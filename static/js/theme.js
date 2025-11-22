// Manejo de tema (dark/light)
(function(){
  const root = document.documentElement;
  const body = document.body;
  const STORAGE_KEY = 'site-theme';
  const switchSelector = '#themeSwitch';

  function applyTheme(theme){
    const isDark = theme === 'dark';
    if(isDark){
      root.setAttribute('data-theme','dark');
      body.classList.add('dark-mode');
    } else {
      root.removeAttribute('data-theme');
      body.classList.remove('dark-mode');
    }
  }
  function detectInitial(){
    const saved = localStorage.getItem(STORAGE_KEY);
    if(saved==='dark' || saved==='light') return saved;
    if(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches){
      return 'dark';
    }
    return 'light';
  }
  function toggle(){
    const current = root.getAttribute('data-theme')==='dark' ? 'dark':'light';
    const next = current==='dark' ? 'light':'dark';
    applyTheme(next);
    try{ localStorage.setItem(STORAGE_KEY,next);}catch(e){console.warn('No se pudo guardar tema',e);}
  }
  function init(){
    applyTheme(detectInitial());
    const btn = document.querySelector(switchSelector);
    if(!btn) return;
    btn.addEventListener('click', e=>{ e.preventDefault(); toggle(); });
    btn.addEventListener('keydown', e=>{ if(e.key===' '||e.key==='Enter'){ e.preventDefault(); toggle(); }});
    if(window.matchMedia){
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e=>{
        const saved = localStorage.getItem(STORAGE_KEY);
        if(saved!=='dark' && saved!=='light') applyTheme(e.matches ? 'dark':'light');
      });
    }
  }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();

