(function() {
  var twittercode = function(d,s,id, callback){var js,fjs=d.getElementsByTagName(s)[0];if(!d.getElementById(id)){js=d.createElement(s);js.id=id;js.src="//platform.twitter.com/widgets.js";js.onload=callback;fjs.parentNode.insertBefore(js,fjs);}};
  setTimeout(function() {
    twittercode(document,"script","twitter-wjs", function() {
      document.getElementById('buttons').style.display = 'block';
    });
  }, 1000);
})();
