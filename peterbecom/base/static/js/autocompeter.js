'use strict';

(function() {
  function injectAutocompeterJS() {
    var script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/autocompeter/1/autocompeter.min.js';
    script.onload = function() {
      window.Autocompeter(inputElement, {
        url: '/autocompete/v1',
        domain: document.location.host,
        ping: false,
      });
    };
    document.head.appendChild(script);
  }

  var injectedJS = false;
  function onFocusInput(event) {
    if (!injectedJS) {
      injectedJS = true;
      inputElement.removeEventListener('mouseover', onFocusInput, false);
      injectAutocompeterJS();
    }
    return true;
  }

  var inputElement = document.querySelector('[name="q"]');
  if (inputElement) {
    inputElement.addEventListener('mouseover', onFocusInput, false);
  }
})();
