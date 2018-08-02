(function() {
  var attempts = 0;
  var loop = function() {
    if (typeof _bsa !== 'undefined' && _bsa) {
      _bsa.init('default', 'CKYD52JJ', 'placement:peterbecom', {
        target: '.bsa-cpc',
        align: 'horizontal',
        disable_css: 'true'
      });
    } else {
      attempts++;
      if (attempts < 10) {
        setTimeout(loop, 500);
      }
    }
  };
  var inject = function(cb) {
    var script = document.createElement('script');
    script.src = 'https://m.servedby-buysellads.com/monetization.js';
    script.async = true;
    script.onload = cb;
    document.head.appendChild(script);
  };
  function isMobileDevice() {
    return (
      typeof window.orientation !== 'undefined' ||
      navigator.userAgent.indexOf('IEMobile') !== -1
    );
  }
  if (document.querySelector('div.bsa-cpc') && !isMobileDevice()) {
    inject(loop);
  }
})();
