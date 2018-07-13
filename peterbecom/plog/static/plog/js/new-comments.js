$(function() {
  $('.comments').on('click', '.delete-button, .approve-button', function(
    event
  ) {
    event.preventDefault();

    $(this).addClass('loading');
    $(this).addClass('disabled');
    var button = $(this);
    var url = button.data('url');

    $.post(url, {
      csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val()
    })
      .done(function() {
        button
          .parent('.approval')
          .text(url.indexOf('/delete/') === -1 ? 'Approved' : 'Deleted');
      })
      .fail(function(jqXHR, textStatus, errorThrown) {
        throw new Error('Status ' + textStatus + ' errorThrown ' + errorThrown);
      });
  });

  $('.comments').on('click', 'input.all-unchecked', function(event) {
    var checkBoxes = $('.comment input[type="checkbox"]');
    checkBoxes.prop('checked', !checkBoxes.prop('checked'));
  });

  var approveAllUrl = $('.comments').data('approve-all-url');
  var deleteAllUrl = $('.comments').data('delete-all-url');
  $('.comments').on('click', '.approve-all-button', function(event) {
    event.preventDefault();
    _batch(this, 'approve');
  });

  $('.comments').on('click', '.delete-all-button', function(event) {
    event.preventDefault();
    _batch(this, 'delete');
  });

  function _batch(button, action) {
    var ids = [];
    var formData = new FormData();
    formData.append(
      'csrfmiddlewaretoken',
      $('input[name="csrfmiddlewaretoken"]').val()
    );
    $('input[name="ids"]:checked').each(function() {
      var id = $(this).val();
      $('button', $(this).parent())
        .addClass('loading')
        .addClass('disabled');
      ids.push(id);
    });
    formData.append('ids', ids);
    var url = action === 'approve' ? approveAllUrl : deleteAllUrl;
    if (ids.length) {
      fetch(url, {
        method: 'POST',
        body: formData
      })
        .then(function(r) {
          r.json();
        })
        .then(function(result) {
          $('input[name="ids"]:checked').each(function() {
            $(this)
              .parent('.approval')
              .text(action === 'approve' ? 'Approved' : 'Deleted');
          });
        });
    }
  }
});
