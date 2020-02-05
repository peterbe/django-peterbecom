(function() {
  var container = $('#awspa');

  // http://youmightnotneedjquery.com/#fade_in
  function fadeIn(el) {
    el.style.opacity = 0;
    el.style.display = ''; // peterbe added

    var last = +new Date();
    var tick = function() {
      el.style.opacity = +el.style.opacity + (new Date() - last) / 400;
      last = +new Date();

      if (+el.style.opacity < 1) {
        (window.requestAnimationFrame && requestAnimationFrame(tick)) ||
          setTimeout(tick, 16);
      }
    };
    tick();
  }

  function loadAwspa(url) {
    fetch(url)
      .then(function(r) {
        if (r.ok) {
          r.text().then(function(response) {
            container.html(response);
            var imagesToLoad = 0;
            $('img', container).each(function() {
              imagesToLoad++;
              var i = new Image();
              i.onload = function() {
                imagesToLoad--;
                if (!imagesToLoad) {
                  fadeIn(container[0]);
                }
              };
              i.src = this.src;
            });
          });
        }
      })
      .catch(function(err) {
        console.error('Failure to fetch', url, 'error:', err);
      });
  }
  if ($ && window.fetch) {
    // only if jQuery has loaded and if window.fetch exists
    var url = document.location.pathname.replace(/\/p\d+$/g, '') + '/awspa';
    loadAwspa(url, true);
  }
})();
