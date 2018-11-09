(function() {
  'use strict';

  window.setTimeout(function() {
    var links = document.getElementsByTagName('link');
    var len = links.length;
    for (var i = 0; i < len; i++) {
      var link = links[i];
      if (link.rel === 'preload' && link.getAttribute('media') === 'delayed') {
        link.setAttribute('media', 'all');
        link.rel = 'stylesheet';
      }
    }
  }, 1000);
})();
