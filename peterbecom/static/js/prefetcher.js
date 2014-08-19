$(function() {
  var prefetched = [];
  var prefetch_timer = null;
  $('div.navbar, div.content').on('mouseover', 'a', function(e) {
    var value = e.target.attributes.href.value;
    if (value.indexOf('/') === 0) {
      if (prefetched.indexOf(value) === -1) {
        if (prefetch_timer) {
          clearTimeout(prefetch_timer);
        }
        prefetch_timer = setTimeout(function() {
          $.get(value, function() {
            // necessary for $.ajax to start the request :(
          });
          prefetched.push(value);
        }, 200);
      }
    }
  }).on('mouseout', 'a', function(e) {
    if (prefetch_timer) {
      clearTimeout(prefetch_timer);
    }
  });
});
