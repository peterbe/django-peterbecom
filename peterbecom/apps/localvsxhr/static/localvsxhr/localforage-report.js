var TIME_TO_BOOT1, TIME_TO_BOOT2;
var a = performance.now();
localforage.getItem('anything',function() {
  var b = performance.now();
  localforage.getItem('anything2', function() {
    var c = performance.now();
    TIME_TO_BOOT1 = b - a;
    TIME_TO_BOOT2 = c - b;
  });
});

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
    //console.log(response.items.length, response.count);
    if (prime) {
      localforage.setItem('blogposts', response, function() { console.log('Stored!') });
    } else {
      reportTime('ajax', b - a);
      //console.log("Bytes retrieved:", JSON.stringify(response).length);
      $('#size').text(JSON.stringify(response).length);
    }
  });
}

function downloadByLocalForage() {
  var a = performance.now();
  localforage.getItem('blogposts').then(function(response) {
    if (response === null) {
      downloadByXHR(true);
      alert("First we have to prime the IndexedDB. Reload this page.");
      // window.location.reload();
      return;
    }
    var b = performance.now();
    reportTime('indexeddb', b - a);
    $('#size').text(JSON.stringify(response).length);
  });
}

setTimeout(downloadByXHR);
setTimeout(downloadByLocalForage);

var times = 5;  // make it odd for the sake of median calculation
var start_times = times;
$('#iterations').text(times);
var interval = setInterval(function() {
    setTimeout(downloadByXHR);
    setTimeout(downloadByLocalForage);
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
