function reportTime(what, time) {
    $('#' + what).append(
        $('<td>').text(time.toFixed(2) + 'ms').data('time', time)
     );
}

$(function() {

  $('.share button').on('click', function() {
    // this depends on the global `medians` dictionary
    // console.log(medians);
    var data = {
      url: location.href,
      user_agent: navigator.userAgent,
      local_median: medians.IndexedDB || medians.localStorage,
      xhr_median: medians.AJAX,
      plain_localstorage: medians.localStorage && 'true',
      iterations: start_times,
    };
    // console.log(data);
    $.post('/localvsxhr/store', data)
    .done(function() {
      $(this).hide();
      $('.share button').hide();
      $('.share .error').hide();
      $('.share p').show();
    }).error(function() {
      $('.share .error').show();
    });

  });

});
