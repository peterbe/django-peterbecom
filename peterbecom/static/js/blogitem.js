function L() {
  if (window.console && window.console.log)
    console.log.apply(console, arguments);
}

var F = (function() {
  var form = $('form#comment');
  var preview = $('#preview-comment-outer');

  function commentData() {
    return {
       name: $('input[name="name"]', form).val(),
       email: $('input[name="email"]', form).val(),
       parent: $('input[name="parent"]', form).val(),
       comment: $('textarea', form).val(),
       csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]', form).val()
    };
  }

  return {
     prepare: function() {
       $.getJSON('/plog/prepare.json', function(response) {
         $('input[name="csrfmiddlewaretoken"]', form).val(response.csrf_token);
         if (response.name) {
           $('input[name="name"]', form).val(response.name);
         }
         if (response.email) {
           $('input[name="email"]', form).val(response.email);
         }
       });
     },
    setup_reply: function(parent) {
      form.detach().insertAfter($('.commenttext:eq(0)', parent));
      preview.detach().insertBefore(form);
      $('input[name="parent"]', form).val(parent.attr('id'));
      $('p.cancel:hidden', form).show();
      F.prepare();

    },
    reset: function() {
      $('.cancel:visible', form).hide();
      $('textarea', form).val('');
      $('input[name="parent"]', form).val('');
      $('#comments-outer').append(form.detach());
      form.insertBefore(preview.detach());
      return false;
    },
    preview: function(callback) {
      preview.hide();
      $.ajax({
         url: '/plog/preview.json',
        data: commentData(),
        type: 'POST',
        dataType: 'json',
        success: function(response) {
          preview
            .html(response.html)
            .fadeIn(300);

          callback();
        },
        error: function (jqXHR, textStatus, errorThrown) {
          alert('Error: ' + errorThrown);
        }
      });
    },
    submit: function() {
      $.ajax({
         url: form.attr('action'),
        data: commentData(),
        type: 'POST',
        dataType: 'json',
        success: function(response) {
          var parent;
          if (response.parent) {
            parent = $('.commenttext:eq(0)', $('#' + response.parent));
          } else {
            parent = $('#comments-outer');
          }
          parent.append(response.html);
          $('textarea', form).val('');
          F.reset();
        },
        error: function (jqXHR, textStatus, errorThrown) {
          alert('Error: ' + errorThrown);
        }
      });
      return false;
    }
  }
})();

$(function() {
  var form = $('form#comment');

  $(window).on('scroll', function() {
    $(window).off('scroll');
    $('form#comment').off('mouseover');
    F.prepare();
  });

  form.on('mouseover', function() {
    $(window).off('scroll');
    $(this).off('mouseover');
    F.prepare();
  });

  form.on('mouseover', function() {
    $(window).off('scroll');
    $(this).off('mouseover');
    F.prepare();
  });

  $('button.preview', form).click(function() {
    if ($('textarea', form).val()) {
      F.preview(function() {
        $('button.preview', form).removeClass('primary');
        $('button.post', form).addClass('primary');
      });
    }
    return false;
  });

  $('a.reply', '#comments-outer').on('click', function() {
    F.setup_reply($('#' + $(this).attr('data-oid')));
    return false;
  });

  form.on('submit', F.submit);
  $('.cancel a', form).on('click', F.reset);

});
