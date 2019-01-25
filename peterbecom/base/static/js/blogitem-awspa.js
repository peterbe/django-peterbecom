(function() {
  var container = $('#awspa');

  function loadAwspa(url) {
    container.load(url, function() {
      var imagesToLoad = 0;

      $('img', container).each(function() {
        imagesToLoad++;
        var i = new Image();
        i.onload = function() {
          imagesToLoad--;
          if (!imagesToLoad) {
            container.hide().fadeIn(300);
          }
        };
        i.src = this.src;
      });

      var asins = [];
      $('.item', container).each(function(i, item) {
        asins.push('' + $(item).data('asin'));
      });
      if (asins.length && window.sessionStorage) {
        $('<button class="mini ui button">')
          .addClass('refresh')
          .data('prefetcher', 'no')
          .text('Refresh products')
          .on('click', function(event) {
            event.preventDefault();
            $(this)
              .text('Refreshing...')
              .addClass('disabled');

            var loaded = JSON.parse(
              window.sessionStorage.getItem('loadedawspa') || '{}'
            );
            var oid = document.location.pathname.split('/')[2];
            loaded[oid] = asins;
            window.sessionStorage.setItem(
              'loadedawspa',
              JSON.stringify(loaded)
            );

            var newURL =
              url.split('?')[0] + '?' + $.param({ seen: asins }, true);
            container.hide();
            loadAwspa(newURL);
          })
          .appendTo(container);
      }
    });
  }
  if ($) {
    // only if jQuery has loaded
    loadAwspa(document.location.pathname + '/awspa', true);
  }
})();
