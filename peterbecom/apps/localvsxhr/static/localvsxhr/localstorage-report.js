
var medians = {};
function summorize() {
  $('.container .summary').append(
    $('<h3>').text('Summary:')
  );
  $('tr').each(function() {
    var sum = 0.0;
    var iterations = 0;
    var label = $('th', this).eq(0).text();
    var times = [];
    $('td', this).each(function() {
      sum += $(this).data('time');
      times.push($(this).data('time'));
      iterations++;
    });
    $('.container .summary').append(
        $('<h3>').text(label)
    );

    $('.container .summary').append(
        $('<h4>').text('Average: ' + (sum/iterations).toFixed(2) + 'ms')
    );
    times.sort();
    var median = times[Math.floor(times.length / 2)];
    medians[label] = median;
    $('.container .summary').append(
        $('<h4>').text('Median: ' + median.toFixed(2) + 'ms')
    );
  });
  $('.container .share').show();
}

function downloadByXHR(prime) {
  prime = prime || false;
  var a = performance.now();
  $.ajax({url: '/blogposts.json', cache: false}).then(function(response) {
    var b = performance.now();
    if (prime) {
      localStorage.setItem('blogposts', JSON.stringify(response));
    } else {
      reportTime('ajax', b - a);
      $('#size').text(JSON.stringify(response).length);
    }
  });
}

function downloadByLocalStorage() {
  var a = performance.now();
  var result = localStorage.getItem('blogposts');
  if (result === null) {
      downloadByXHR(true);
      alert("First we have to prime the localStorage. Reload this page.");
      return;
  }
  var asObject = JSON.parse(result);
  var b = performance.now();
  reportTime('local', b - a);
  $('#size').text(JSON.stringify(asObject).length);

}

setTimeout(downloadByXHR);
setTimeout(downloadByLocalStorage);

var times = 5;  // make it odd for the sake of median calculation
var start_times = times;
$('#iterations').text(times);
var interval = setInterval(function() {
    setTimeout(downloadByXHR);
    setTimeout(downloadByLocalStorage);
    times--;
    $('#iterations').text(times);
    if (times == 0) {
      clearInterval(interval);
      $('.container .summary').append(
          $('<p>').text("Done.")
      );
      summorize();

    }
}, 4 * 1000);
