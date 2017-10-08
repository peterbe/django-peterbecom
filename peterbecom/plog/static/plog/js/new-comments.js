$(function() {
  $('.comments').on('click', '.delete-button', function(event) {
    event.preventDefault();

    $(this).addClass('loading');
    $(this).addClass('disabled');
    var button = $(this);
    var url = button.data('url');

    $.post(url, {csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val()})
    .done(function() {
      button.parent('.approval').text(
        url.indexOf('/delete/') === -1 ? 'Approved' : 'Deleted'
      );
    })
    .fail(function( jqXHR, textStatus, errorThrown ) {
      throw new Error('Status ' + textStatus + ' errorThrown ' + errorThrown);
    });
  });
});
