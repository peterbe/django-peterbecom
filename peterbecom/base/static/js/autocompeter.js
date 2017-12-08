(function() {
  var script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/autocompeter/1/autocompeter.min.js';
  script.onload = function() {
    window.Autocompeter(
      document.querySelectorAll('[name="q"]')[0],
      {url: '/autocompete/v1', domain: document.location.host}
    );
  };
  document.head.appendChild(script);
})();
