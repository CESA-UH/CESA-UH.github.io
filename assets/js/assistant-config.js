// Public application address only. Never put an API key or account password here.
window.ECEAssistant = {
  backendUrl: 'https://40ccb43b7c4fa1.lhr.life',
  urlFor: function(key) {
    var local = /^(127\.0\.0\.1|localhost)$/.test(location.hostname);
    var hostedTogether = location.pathname.indexOf('/docs-site/') === 0 || new URL(document.baseURI).pathname.indexOf('/docs-site/') === 0;
    var base = hostedTogether ? location.origin : local ? 'http://127.0.0.1:8000' : this.backendUrl;
    try {
      var url = new URL(base);
      if (url.protocol !== 'https:' && !(url.protocol === 'http:' && /^(127\.0\.0\.1|localhost)$/.test(url.hostname))) return null;
      url.search = '';
      url.hash = '';
      url.pathname = '/login';
      url.searchParams.set('site_course', key);
      return url.href;
    } catch (_) { return null; }
  }
};
