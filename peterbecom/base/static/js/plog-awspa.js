// From https://gist.github.com/kares/956897
/**
 * $.parseParams - parse query string paramaters into an object.
 */
(function($) {
var re = /([^&=]+)=?([^&]*)/g;
var decodeRE = /\+/g;  // Regex for replacing addition symbol with a space
var decode = function (str) {return decodeURIComponent( str.replace(decodeRE, " ") );};
$.parseParams = function(query) {
    var params = {}, e;
    while ( e = re.exec(query) ) {
        var k = decode( e[1] ), v = decode( e[2] );
        if (k.substring(k.length - 2) === '[]') {
            k = k.substring(0, k.length - 2);
            (params[k] || (params[k] = [])).push(v);
        }
        else params[k] = v;
    }
    return params;
};
})(jQuery);



$(function() {
  var asins = window.__product_asins__;


  var qs = $.parseParams( document.location.search.split('?')[1] || '' );
  if (qs.focus) {
    $('input[name="keyword"]').each(function(i, el) {
      if ($(this).val() === qs.focus) {
        $(el).parent()[0].scrollIntoView();
      }
    });
  } else if (qs.error) {
    var error = JSON.parse(qs.error);
    var container = $('div.ui.negative.message')
    $('.header', container).text(error.Code);
    $('p', container).text(error.Message);
    container.show();
  }

  // Change all "Pick" buttons to highlight those already associated
  // with this blog post.
  function _highlightPickedButtons(asins) {
    // Reset
    $('.item div.button.primary').text('Pick').removeClass('primary');

    // Highlight those in 'asins'
    $.each(asins, function(i, asin) {
      $(`.item[data-asin="${asin}"] div.button`)
      .addClass('primary')
      .text('Picked');
    });
  }
  // Once upon load
  _highlightPickedButtons(asins);

  $('.all-keywords').on('click', '.item .extra div.button', function() {
    var button = $(this);
    var item = button
      .parent()
      .parent()
      .parent();
    // If it's an ASIN that is all numbers, jQuery will think it's a number
    var asin = '' + item.data('asin');
    if (asins.includes(asin)) {
      asins = asins.filter(function(oldAsin) {
        return oldAsin !== asin;
      })
    } else {
      asins.push(asin);
    }
    var data = {}
    _highlightPickedButtons(asins);

    // Save it on the server
    data.asins = asins;
    data.csrfmiddlewaretoken = $('input[name="csrfmiddlewaretoken"]').val();
    var serializedObj = $.param(data, true);
    $.post(document.location.pathname, serializedObj)
    .done(function(response) {
      // console.log('Saved', response);
    })
    .fail(function(error) {
      throw new Error(error)
    })
  });

  $('.all-keywords').on('click', '.loadmore button', function(event) {
    $(this).addClass('loading');
  });

});
