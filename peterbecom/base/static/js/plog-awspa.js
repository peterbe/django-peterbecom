$(function() {
  var qs = new URLSearchParams(document.location.search.split('?')[1] || '');
  if (qs.has('focus')) {
    $('input[name="keyword"]').each(function(i, el) {
      if ($(this).val() === qs.get('focus')) {
        $(el)
          .parent()[0]
          .scrollIntoView();
      }
    });
    if (qs.getAll('new').length) {
      var alertMsg = 'NEW TITLES:\n';
      qs.getAll('new').forEach(title => {
        alertMsg += `  * ${title}\n`;
      });
      alert(alertMsg);
    }
  } else if (qs.error) {
    var error = JSON.parse(qs.error);
    var container = $('div.ui.negative.message');
    $('.header', container).text(error.Code);
    $('p', container).text(error.Message);
    container.show();
  }

  function _highlightDisabled() {
    $('.all-keywords .item').each(function() {
      var item = $(this);
      if (item.data('disabled')) {
        item.addClass('disabled');
      } else {
        item.removeClass('disabled');
      }
    });
  }
  _highlightDisabled();

  // Attach some action buttons on each.
  $('.all-keywords .keyword').each(function() {
    var keyword = $('input[name="keyword"]', this).val();

    var parent = this;
    $('.item', this).each(function() {
      var item = $(this);
      var disabled = item.data('disabled');
      var asin = item.data('asin');
      var buttons = $('<div class="ui right floated">');
      buttons.append(
        $('<div class="ui button action">')
          .text(disabled ? 'Enable' : 'Disable')
          .on('click', function() {
            item.data('disabled', !item.data('disabled'));
            toggleDisabled(keyword, asin);
          })
      );
      buttons.append(
        $('<div class="ui button delete">')
          .text('Delete')
          .on('click', function() {
            // item.data('disabled', !item.data('disabled'));
            if (1 || confirm('Really?')) {
              deleteItem(keyword, asin, parent).done(function() {
                item.remove();
              });
            }
          })
      );
      $('.content', this).prepend(buttons);
    });
  });

  function toggleDisabled(keyword, asin) {
    var data = {};
    data.asin = asin;
    data.keyword = keyword;
    data.csrfmiddlewaretoken = $('input[name="csrfmiddlewaretoken"]').val();
    var serializedObj = $.param(data, true);
    return $.post('/awspa/keywords', serializedObj)
      .done(function(response) {
        _highlightDisabled();
      })
      .fail(function(error) {
        throw new Error(error);
      });
  }

  function deleteItem(keyword, asin) {
    var data = {};
    data.asin = asin;
    data.keyword = keyword;
    data.csrfmiddlewaretoken = $('input[name="csrfmiddlewaretoken"]').val();
    var serializedObj = $.param(data, true);
    return $.post('/awspa/delete', serializedObj).fail(function(error) {
      throw new Error(error);
    });
  }

  $('.all-keywords').on('click', '.loadmore button', function(event) {
    $(this).addClass('loading');
  });
});
