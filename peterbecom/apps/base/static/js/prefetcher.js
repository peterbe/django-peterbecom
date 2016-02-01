/*global $*/
$(function() {
  'use strict';

  var prefetched = [];
  var prefetchTimer = null;
  $('.container').on('mouseover', 'a', function(e) {
    if (!e.target.attributes.href) {
      return;
    }
    if (e.target.attributes.rel && e.target.attributes.rel.value === 'nofollow') {
      return;
    }
    var value = e.target.attributes.href.value;
    if (value.indexOf('/') === 0) {
      if (prefetched.indexOf(value) === -1) {
        if (prefetchTimer) {
          clearTimeout(prefetchTimer);
        }
        prefetchTimer = setTimeout(function() {
          $.get(value, function() {
            // necessary for $.ajax to start the request :(
          });
          prefetched.push(value);
        }, 200);
      }
    }
  }).on('mouseout', 'a', function() {
    if (prefetchTimer) {
      clearTimeout(prefetchTimer);
    }
  });
});
