(function() {
  window.setTimeout(function() {

    if ($) {
      $.getJSON('https://songsear.ch/api/search/examples')
      .done(function(response) {
        if (!response) {
          return;
        }
        if (!response.examples.length) {
          return;
        }
        var container = $('<div>').css('margin-top', '100px').css('margin-bottom', '50px');
        container.append($('<p>Song example lyrics searches...</p>'));
        var ul = $('<ul>').css('list-style-image', 'url("https://songsearch-2916.kxcdn.com/static/bullet.png")');
        $.each(response.examples, function(i, example) {
          var href = 'https://songsear.ch/q/' + encodeURIComponent(example.term);
          $('<li>')
            .append($('<a>').attr('href', href).text(example.term))
            .appendTo(ul);
        });
        container.append(ul);
        $('.ui.text.container.content').append(container);
      });
    }

  }, 1600);

})();
