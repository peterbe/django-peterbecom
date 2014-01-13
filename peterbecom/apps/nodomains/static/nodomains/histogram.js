google.load("visualization", "1", {packages:["corechart"]});
google.setOnLoadCallback(draw_histogram);


function draw_histogram() {
  $.get('histogram')
    .then(function(results) {
      var data = google.visualization.arrayToDataTable(results);
      var options = {
         title: 'Histogram of number of domains per URL',
        legend: { position: 'none' },
      };

      var chart = new google.visualization.Histogram(document.getElementById('histogram'));
      chart.draw(data, options);

    });
}
