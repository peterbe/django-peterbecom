var timer = null;
function startLoadingTimer() {
  $('#seconds').text('0');
  if (timer) clearInterval(timer);
  timer = setInterval(function() {
    var s = parseInt($('#seconds').text(), 10);
    s++;
    $('#seconds').text(s);
  }, 1000);
}

function stopLoadingTimer() {
  if (timer) clearInterval(timer);
}


$(function() {

  var resubmit_interval, countdown_interval;

  $('input[name="url"]').change(function() {
    $('#error_output').hide();
    $('#result_output').hide();
  });

  $('form.form-submit').submit(function() {
    if (resubmit_interval) clearInterval(resubmit_interval);
    if (countdown_interval) clearInterval(countdown_interval);
    $('#error_output').hide();
    $('#result_output').hide();
    $('#queued_output').hide();
    var url = $('input[name="url"]').val().trim();
    if (url) {
      var params = {
        url: url,
        csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val()
      };
      $('#loading').show();
      startLoadingTimer();
      $.post('run', params)
        .then(function(result) {
          //console.log('RESULT', result);
          if (result.error) {
            $('#error_output pre').text(result.error);
            $('#error_output').show();
          } else if (!result.count) {
            $('#queued_output .behind').text(result.behind);
            $('#queued_output').show();
            resubmit_interval = setInterval(function() {
              $('form.form-submit').submit();
            }, 10 * 1000);
            $('.countdown').text('10');
            countdown_interval = setInterval(function() {
              $('.countdown').each(function(i, e) {
                var $e = $(e);
                var prev = parseInt($e.text());
                $e.text('' + (prev - 1));
              });
            }, 1000);
          } else {
            $('input[name="url"]').val('');
            $('#result_output .count').text(result.count);
            $('#result_output li').remove();
            $.each(result.domains, function(i, d) {
              $('#result_output ul')
                .append($('<li>').append($('<code>').text(d)));
            });
            $('#result_output').show();
            var container = $('#recently tbody');
            $('<tr>')
              .append($('<td>')
                      .append($('<a href="#">+</a>')
                              .addClass('expander')
                              .addClass('btn').addClass('btn-mini')
                              .data('url', url)
                              .click(expandURL)))
              .append($('<td>').append($('<a target="_blank">')
                               .attr('href', url)
                               .text(url)))
              .append($('<td>').text(result.count))
              .prependTo(container);

          }
        }).fail(function(jqXHR, textStatus, errorThrown) {
          console.warn('Error!');
          console.log('textStatus', textStatus);
          console.log('errorThrown', errorThrown);
          var msg = "Some server error happened. Basically, my fault.";
          if (errorThrown === 'Gateway Time-out') {
            msg += "\nIt timed out. It probably means my server took too long to download the page.";
          }
          $('#error_output pre').text(msg);
          $('#error_output').show();
        }).always(function() {
          stopLoadingTimer();
          $('#loading').hide();
        });
    }
    return false;
  });

  // pull down the numbers
  $.get('numbers')
    .then(function(result) {
      var container = $('#numbers');
      $('.numbers-average', container).text(result.average);
      $('.numbers-median', container).text(result.median);
      $('.numbers-stddev', container).text(result.stddev);
      $('.numbers-total', container).text(result.total);
      $('#numbers').show();
    });

  // pull down the most common
  $.get('most-common')
    .then(function(result) {
      var container = $('#most_common tbody');
      $.each(result, function(i, row) {
        $('<tr>')
          .append($('<td>').text(row[0]))
          .append($('<td>').text(row[1]))
          .appendTo(container);
      });
      $('#most_common').show();
    });

  function _addToRecently(url, count, container) {
    container = container || $('#recently tbody');

  }

  function expandURL() {
    var e = $(this);
    var tr = e.parents('tr');

    if (e.text() == '+') {
      if ($('.domains', tr).length) {
        $('.domains', tr).show();
      } else {
        var td = $('td', tr).eq(1);
        var url = e.data('url');
        $.get('domains', {url: url})
          .then(function(result) {
            var c = $('<ul>')
                     .addClass('domains');
            $.each(result.domains, function(i, domain) {
              c.append($('<li>').text(domain));
            });
            c.appendTo(td);
          }).fail(function() {
            alert("Sorry. Something went terribly wrong.");
          });
      }
      e.text('-');
    } else {
      $('.domains', tr).hide();
      e.text('+');
    }
    return false;
  }

  // pull down recent ones
  $.get('recently')
    .then(function(result) {
      $('#recently').show();
      var container = $('#recently tbody');
      $.each(result.recent, function(i, row) {
        var url = row[0];
        var count = row[1];
        $('<tr>')
          .append($('<td>')
                  .append($('<a href="#">+</a>')
                          .addClass('expander')
                          .addClass('btn').addClass('btn-mini')
                          .data('url', url)
                          .click(expandURL)))
          .append($('<td>').append($('<a target="_blank">')
                               .attr('href', url)
                               .text(url)))
          .append($('<td>').text(count))
          .appendTo(container);
      });
    });

  // pull down the hall of fame
  $.get('hall-of-fame')
    .then(function(result) {
      $('#hall_of_fame').show();
      var container = $('#hall_of_fame tbody');
      $.each(result, function(i, row) {
        $('<tr>')
          .append($('<td>')
                  .append($('<a href="#">+</a>')
                          .addClass('expander')
                          .addClass('btn').addClass('btn-mini')
                          .data('url', row[0])
                          .click(expandURL)))
          .append($('<td>').append($('<a target="_blank">')
                                   .attr('href', row[0])
                                   .text(row[0])))
          .append($('<td>').text(row[1]))
          .appendTo(container);
      });
    });

});
