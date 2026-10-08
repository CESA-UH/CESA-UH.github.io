function themeControl(){
  const dark=document.documentElement.dataset.theme==='dark';
  const path=dark?'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>':'<path d="M21 13a9 9 0 0 1-10-10 9 9 0 1 0 10 10Z"/>';
  return `<button class="theme-toggle" data-action="toggle-theme" type="button" aria-label="${dark?'تغییر به حالت روشن':'تغییر به حالت تاریک'}" aria-pressed="${dark}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true">${path}</svg><span>پوسته</span></button>`;
}
document.addEventListener('click',event=>{
  if(!event.target.closest('[data-action="toggle-theme"]'))return;
  const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';
  document.documentElement.dataset.theme=theme;
  localStorage.setItem('ece-docs-theme',theme);
  const template=document.createElement('template');template.innerHTML=themeControl();
  const updated=template.content.firstElementChild;
  document.querySelectorAll('[data-action="toggle-theme"]').forEach(button=>{
    button.innerHTML=updated.innerHTML;
    button.setAttribute('aria-label',updated.getAttribute('aria-label'));
    button.setAttribute('aria-pressed',updated.getAttribute('aria-pressed'));
  });
});
