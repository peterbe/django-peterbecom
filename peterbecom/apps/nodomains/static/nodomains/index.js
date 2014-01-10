var timer = null;
function startLoadingTimer() {
  $('#seconds').text('0');
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

  $('input[name="url"]').change(function() {
    $('#error_output').hide();
    $('#result_output').hide();
  });

  $('form.form-submit').submit(function() {
    $('#error_output').hide();
    $('#result_output').hide();
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
          console.log('RESULT', result);
          if (result.error) {
            $('#error_output pre').text(result.error);
            $('#error_output').show();
          } else {
            $('#result_output .count').text(result.count);
            $('#result_output li').remove();
            $.each(result.domain, function(i, d) {
              $('#result_output ul')
                .append($('<li>').append($('<code>').text(d)));
            });
            $('#result_output').show();
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
});
