function reportTime(what, time) {
    $('#' + what).append(
        $('<td>').text(time.toFixed(2) + 'ms').data('time', time)
     );
}

$(function() {

  $('.share button').on('click', function() {
    // this depends on the global `medians` dictionary
    var driver = null;
    if (typeof localforage !== 'undefined') {
      driver = localforage.driver();
    }
    var data = {
      csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val(),
      url: location.href,
      user_agent: navigator.userAgent,
      local_median: medians.IndexedDB || medians.localStorage || medians['localForage(localStorage driver)'],
      xhr_median: medians.AJAX,
      plain_localstorage: medians.localStorage && 'true' || '',
      iterations: start_times,
      driver: driver,
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

    if (typeof TIME_TO_BOOT1 !== 'undefined' && typeof TIME_TO_BOOT2 !== 'undefined') {
      data = {
        csrfmiddlewaretoken: data.csrfmiddlewaretoken,
        time_to_boot1: TIME_TO_BOOT1,
        time_to_boot2: TIME_TO_BOOT2,
        plain_localstorage: typeof localforage === 'undefined',
        driver: driver,
      };
      $.post('/localvsxhr/store/boot', data)
      .done(function() {
        console.log('Stored Time to boot', TIME_TO_BOOT1, TIME_TO_BOOT2);
      });
    }

  });

});
