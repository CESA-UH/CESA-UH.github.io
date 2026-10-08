window.ECESiteCourseKey="CI-Fall-1405-1406";
(function(){
  function mount(){
    var content=document.querySelector('.md-content__inner');
    if(!content||document.querySelector('.course-assistant-entry'))return;
    var url=window.ECEAssistant&&window.ECEAssistant.urlFor("CI-Fall-1405-1406");
    if(!url)return;
    var panel=document.createElement('aside');panel.className='course-assistant-entry';
    var link=document.createElement('a');link.href=url;link.target='_blank';link.rel='noopener noreferrer';
    link.textContent='دستیار این درس، کوییز و مسیر مطالعهٔ من ←';panel.appendChild(link);content.before(panel);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
