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
    });
  }
  if ($) {
    // only if jQuery has loaded
    var url = document.location.pathname.replace(/\/p\d+$/g, '') + '/awspa';
    loadAwspa(url, true);
  }
})();
