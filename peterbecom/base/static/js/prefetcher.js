/*global $*/
$(function() {
  'use strict';

  function preFetchImage(url, callback) {
    var img = new Image();
    img.onload = function() {
      callback(url);
    };
    img.src = url;
  }

  var prefetched = [];
  var prefetchTimer = null;
  $('.container')
    .on('mouseover', 'a', function(e) {
      if (!e.target.attributes.href) {
        return;
      }
      if (
        e.target.attributes.rel &&
        e.target.attributes.rel.value === 'nofollow'
      ) {
        return;
      }
      var value = e.target.attributes.href.value;
      if (value.indexOf('/') === 0) {
        if (prefetched.indexOf(value) === -1) {
          if (prefetchTimer) {
            clearTimeout(prefetchTimer);
          }
          prefetchTimer = setTimeout(function() {
            $.get(value).done(function(response) {
              var imageRegex = /<img.*?src="([^">]*\/([^">]*?))".*?>/g;
              var match;
              while ((match = imageRegex.exec(response))) {
                var url = match[1];
                if (prefetched.indexOf(url) === -1 && prefetched.length < 5) {
                  if (url.indexOf('cdn-2916.kxcdn.com') > -1) {
                    // Add it immediately, instead of waiting for the
                    // async loading.
                    prefetched.push(url);
                    preFetchImage(url, function(url) {
                      // Nothing to do at the moment.
                    });
                  }
                }
              }
            });
            prefetched.push(value);
          }, 200);
        }
      }
    })
    .on('mouseout', 'a', function() {
      if (prefetchTimer) {
        clearTimeout(prefetchTimer);
      }
    });
});
