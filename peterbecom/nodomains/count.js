// Inspired by https://gist.github.com/cjoudrey/1341747

var url = phantom.args[0];
var original_domain = getDomain(url);

var maxRenderWait = 10 * 1000;

var page = require('webpage').create()
var count = 0
var forcedRenderTimeout;
var renderTimeout;

var domains = {};

page.viewportSize = { width: 1280, height : 1024 };

page.settings.resourceTimeout = 5000;

console.log('URL', url);
function doRender() {
  //page.render(original_domain + '.png');
  page.render('phantomjs-screenshot.png');
  //page.render();
  phantom.exit();
}

function getDomain(url) {
  return url.split('//')[1].split('/')[0];
}

page.onResourceTimeout = function(e) {
  console.log(e.errorCode);   // it'll probably be 408
  console.log(e.errorString); // it'll probably be 'Network timeout on resource'
  console.log(e.url);         // the url whose request timed out
  phantom.exit(1);
};

page.onResourceRequested = function (req) {
  count += 1;
  if (req.url.substring(0, 5) != 'data:') {
    var domain = getDomain(req.url);
    domains[domain] = (domains[domain] || 0) + 1;
  }
  console.log('> (' + count + ') ' + req.id + ' - ' + req.url.substring(0, 70));
  clearTimeout(renderTimeout);
};

page.onResourceReceived = function (res) {
  if (!res.stage || res.stage === 'end') {
    count -= 1;
    console.log('< (' + count + ') ' + res.id + ' ' + res.status + ' - ' + res.url.substring(0, 70));
  }
};


page.open(url, function (status) {
  if (status !== "success") {
    console.log('Unable to load url');
    phantom.exit();
  } else {
    forcedRenderTimeout = setTimeout(function () {
      console.log(count);
      console.log('In forcedRenderTimeout');
      //doRender();
      var count_domains = 0;
      for (var domain in domains) {
        console.log('DOMAIN:', domain, 'COUNT:', domains[domain]);
        // console.log('DOMAIN:', domain);
        count_domains++;
      }
      console.log('COUNT:', count_domains);
      // console.log(domains);
      phantom.exit();
    }, maxRenderWait);
  }
});
