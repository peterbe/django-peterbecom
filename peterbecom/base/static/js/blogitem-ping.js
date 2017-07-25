(function() {
  window.setTimeout(function() {
    var url = document.location.href + '/ping';
    var pathname = document.location.pathname.split('/');
    var oid = pathname[pathname.length - 1];
    if (window.fetch && window.sessionStorage) {
      var pinged = (window.sessionStorage.getItem('pinged') || '').split('/');
      if (pinged.indexOf(oid) === -1) {
        window.fetch(url, {method: 'PUT'}).then(function(response) {
          if (response.status === 200) {
            pinged.unshift(oid);
            window.sessionStorage.setItem('pinged', pinged.join('/'));
          }
        });
      }
    }
  }, 1000);
})();
