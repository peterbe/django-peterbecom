google.load("visualization", "1", {packages:["corechart"]});
google.setOnLoadCallback(draw_histogram);


function draw_histogram() {
  $.get('histogram')
    .then(function(results) {
      console.dir(results);
      var data = google.visualization.arrayToDataTable(results);
      var options = {
         title: 'Histogram',
        legend: { position: 'none' },
      };

      var chart = new google.visualization.Histogram(document.getElementById('histogram_chart'));
      chart.draw(data, options);
      $('#histogram').show();

    });
}
