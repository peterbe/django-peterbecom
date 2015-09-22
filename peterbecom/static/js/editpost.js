var Preview = (function() {
  'use strict';

  var container = $('form[method="post"]');
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
           error: function(a,b,c) {
             if (c) alert(c);
           },
         success: function(response) {
           $('#preview-container').html(response);
         }
       });

     },
    enough_data: function() {
      if (!$('#id_title').val() || !$('#id_text').val()) {
        return false;
      }
      return true;
    }
  }
})();

var Thumbnails = (function() {
  var oid = location.pathname.split('/').slice(-1)[0];
  return function() {
    if (oid) {
      $.ajax('/plog/thumbnails/' + oid, {
         success: function(response) {
           $('#thumbnails .inner').html(response);
           $('#thumbnails:hidden').show();
         }
      });
    }
  };
})();

function slugify(s) {
  return $.trim(s).replace(/\s+/gi, '-').toLowerCase();
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

    var editor = CodeMirror.fromTextArea(document.getElementById("id_text"), {
      mode: mode,
       lineWrapping: true,
        lineNumbers: true,
        matchBrackets: true,
        onBlur: function() {
          $('#id_text').val(editor.getValue());
          Preview.update();
        }//,
      //theme: "default"
    });
  }

});
