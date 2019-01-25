(function() {
  var container = $('#awspa');

  function loadAwspa(url, hidefirst) {
    if (hidefirst) {
      container.hide();
    }
    container.load(url, function() {
      if (hidefirst) {
        container.fadeIn(400);
      }
      var oid = document.location.pathname.split('/')[2];
      if (window.sessionStorage) {
        var loaded = JSON.parse(
          window.sessionStorage.getItem('loadedawspa') || '{}'
        );
        var asins = [];
        $('.item', container).each(function(i, item) {
          asins.push('' + $(item).data('asin'));
        });
        loaded[oid] = asins;
        window.sessionStorage.setItem('loadedawspa', JSON.stringify(loaded));

        if (asins.length) {
          url = url.split('?')[0];
          var newURL = url + '?' + $.param({ seen: asins }, true);
          $('<button class="mini ui button">')
            .addClass('refresh')
            .data('prefetcher', 'no')
            .text('Refresh products')
            .on('click', function(event) {
              event.preventDefault();
              $(this)
                .text('Refreshing...')
                .addClass('disabled');
              loadAwspa(newURL);
            })
            .appendTo(container);
        }
      }
    });
  }
  window.setTimeout(function() {
    if ($) {
      // only if jQuery has loaded
      loadAwspa(document.location.pathname + '/awspa', true);
    }
  }, 200);
})();
