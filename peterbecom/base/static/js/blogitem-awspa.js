(function() {
  window.setTimeout(function() {
    var url = document.location.href.split('#')[0] + '/awspa';
    $('#awspa').load(url);
  }, 200);
})();
