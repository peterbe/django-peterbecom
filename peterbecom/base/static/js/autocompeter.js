'use strict';

// Idea, only load this IF there's focus on the input[name="q"] at all.

(function() {
  var script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/autocompeter/1/autocompeter.min.js';
  script.onload = function() {
    window.Autocompeter(document.querySelectorAll('[name="q"]')[0], {
      url: '/autocompete/v1',
      domain: document.location.host,
      ping: false,
    });
  };
  document.head.appendChild(script);
})();
