/*global CodeMirror */
var Preview = (function() {
  'use strict';

  var getData = function() {
    var d = {};
    d.oid = $('#id_oid').val();
    d.title = $('#id_title').val();
    d.text = $('#id_text').val();
    d.url = $('#id_url').val();
    d.pub_date = $('#id_pub_date').val();
    d.display_format = $('#id_display_format').val();
    d.categories = $('#id_categories').val();
    return d;
  };

  return {
    update: function() {
      $.ajax('/plog/preview', {
        data: getData(),
        dataType: 'html',
        type: 'POST',
        error: function(a, b, c) {
          if (c) alert(c);
        },
        success: function(response) {
          $('#preview-container').html(response);
        },
      });

    },
    enough_data: function() {
      if (!$('#id_title').val() || !$('#id_text').val()) {
        return false;
      }
      return true;
    },
  };
})();

var Thumbnails = (function() {
  'use strict';
  var oid = location.pathname.split('/').slice(-1)[0];

  function outerHTML(elm) {
    return $('<div>').append(elm.clone()).html();
  }
  return function() {
    if (oid) {
      $.ajax('/plog/thumbnails/' + oid, {
        success: function(response) {
          //  $('#thumbnails-side .inner').html(response);
          $.each(response.images, function(i, image) {
            var img_tag_small = $('<img>')
              .attr('src', image.small.url)
              .attr('alt', image.small.alt)
              .attr('width', image.small.width)
              .attr('height', image.small.height);
            var img_tag_small_html = outerHTML(img_tag_small);
            var ahref_tag_small = $('<a>')
              .attr('href', image.full_url)
              .append(img_tag_small.addClass('floatright'));
            var ahref_tag_small_html = outerHTML(ahref_tag_small);
            var img_tag_big = $('<img>')
              .attr('src', image.big.url)
              .attr('alt', image.big.alt)
              .attr('width', image.big.width)
              .attr('height', image.big.height);
            var img_tag_big_html = outerHTML(img_tag_big);
            var ahref_tag_big = $('<a>')
              .attr('href', image.full_url)
              .append(img_tag_big.addClass('floatright'));
            var ahref_tag_big_html = outerHTML(ahref_tag_big);
            var img_tag_bigger = $('<img>')
              .attr('src', image.bigger.url)
              .attr('alt', image.bigger.alt)
              .attr('width', image.bigger.width)
              .attr('height', image.bigger.height);
            var img_tag_bigger_html = outerHTML(img_tag_bigger);
            var ahref_tag_bigger = $('<a>')
              .attr('href', image.full_url)
              .append(img_tag_bigger.addClass('floatright'));
            var ahref_tag_bigger_html = outerHTML(ahref_tag_bigger);

            $('<div>').addClass('thumbnail-wrapper')
            .append(
              $('<a>')
                .attr('href', '#')
                .data('url', image.delete_url)
                .addClass('delete')
                .text('delete')
            )
            .append($('<br>'))
            .append(
              $('<img>')
                .attr('src', image.small.url)
                .attr('alt', image.small.alt)
                .attr('width', image.small.width)
                .attr('height', image.small.height)
            )
            .append($('<br>'))
            .append(
              $('<span>')
                .text('(' + image.small.width + ',' + image.small.height + ')')
            )
            .append($('<br>'))
            .append(
              $('<input>')
                .attr('title', 'Full size 1000x1000')
                .val(image.small.url)
            )
            .append($('<br>'))
            .append(
              $('<input>')
                .val(img_tag_small_html)
            )
            .append($('<br>'))
            .append(
              $('<input>')
                .val(ahref_tag_small_html)
            )
            .append($('<br>'))
            .append(
              $('<img>')
                .attr('src', image.big.url)
                .attr('alt', image.big.alt)
                .attr('width', image.big.width)
                .attr('height', image.big.height)
            )
            .append($('<br>'))
            .append(
              $('<span>')
                .text('(' + image.big.width + ',' + image.big.height + ')')
            )
            .append($('<br>'))
            .append(
              $('<input>')
                .attr('title', 'Full size 1000x1000')
                .val(image.big.url)
            )
            .append($('<br>'))
            .append(
              $('<input>')
                .val(img_tag_big_html)
            )
            .append($('<br>'))
            .append(
              $('<input>')
                .val(ahref_tag_big_html)
            )
            .append(
              $('<img>')
                .attr('src', image.bigger.url)
                .attr('alt', image.bigger.alt)
                .attr('width', image.bigger.width)
                .attr('height', image.bigger.height)
            )
            .append($('<br>'))
            .append(
              $('<span>')
                .text('(' + image.bigger.width + ',' + image.bigger.height + ')')
            )
            .append($('<br>'))
            .append(
              $('<input>')
                .attr('title', 'Full size 1000x1000')
                .val(image.bigger.url)
            )
            .append($('<br>'))
            .append(
              $('<input>')
                .val(img_tag_bigger_html)
            )
            .append($('<br>'))
            .append(
              $('<input>')
                .val(ahref_tag_bigger_html)
            )
            .appendTo($('#thumbnails-side .inner'));
          });
          if (response.images.length) {
            $('#thumbnails-side h4 .count').text('(' + response.images.length + ')');
            $('#thumbnails-side .toggle').show();
          }
        },
      });
      $('#thumbnails-side').on('click', 'a.toggle', function() {
        $('#thumbnails-side .inner').toggle();
        var current = $(this).text();
        $(this).text(current == 'Show' ? 'Hide' : 'Show');
        return false;
      });
      $('#thumbnails-side').on('click', 'a.delete', function() {
        var data = {
          csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val(),
        };
        var link = $(this);
        $.post(link.data('url'), data, function() {
          link.parents('.thumbnail-wrapper').remove();
          var count = parseInt($('h4 .count').text().replace('(', '').replace(')', ''), 10);
          $('h4 .count').text('(' + (count - 1) +')');
        });
        return false;
      });
    }
  };
})();

function slugify(s) {
  return s.trim().replace(/\s+/gi, '-').replace(/\'/g, '').toLowerCase();
}


var UNIMPORTANT = 'id_display_format,id_codesyntax,id_disallow_comments,id_hide_comments'.split(',');
function toggleUnimportant() {
  UNIMPORTANT.forEach(function(id) {
    $('#' + id).parents('.field').toggle();
  });
}


function slickForm() {
  // Make form really streamlined and space efficient
  $('div.field').each(function() {
    var label = $('label', this).text();
    var input = $('input,textarea', this);
    if (!input.attr('placeholder')) {
      input.attr('placeholder', label);
    }
    if (!input.attr('title')) {
      input.attr('title', label);
    }
  });
  $('div.field label').hide();
}

$(function() {
  $('input, textarea, select', 'form').change(function() {
    if (Preview.enough_data()) {
      Preview.update();
    }
  });
  if (Preview.enough_data()) {
    Preview.update();
  }

  if (!$('#id_oid').val().length) {
    $('#id_title').on('input', function() {
      $('#id_oid').val(slugify($(this).val()));
    });

    $('#id_oid').on('input', function() {
      $('#id_title').off('input');
    });
  }

  Thumbnails();

  var display_format = $('#id_display_format').val();
  if (display_format === 'markdown' || display_format === 'structuredtext') {
    var mode;
    if (display_format == 'markdown')
      mode = 'gfm'; // github flavoured markdown
    else if (display_format == 'structuredtext')
      mode = 'rst'; // reStructuredText

    var editor = CodeMirror.fromTextArea(document.getElementById('id_text'), {
      mode: mode,
      lineWrapping: true,
      lineNumbers: true,
      matchBrackets: true,
      onBlur: function() {
        $('#id_text').val(editor.getValue());
        Preview.update();
      },
    });
  }

  slickForm();
  toggleUnimportant();
  $('#unimportant-toggle').click(function(event) {
    event.preventDefault();
    toggleUnimportant();
    $('div.field label').show();
    $(this).hide();
  });
});
