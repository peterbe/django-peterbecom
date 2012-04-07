function L() {
  if (window.console && window.console.log)
    console.log.apply(console, arguments);
}

var F = (function() {
  var form = $('form#comment');
  var preview = $('#preview-comment-outer');
  var _submitting = false;
  var _preparing = false;

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
       if (_preparing) return;  // to avoid excessive calls
       _preparing = true;
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
      _preparing = false;
      if (parent.size() != 1) throw "Must be exactly 1 parent";
      form.detach().insertAfter($('.ct:eq(0)', parent));
      preview.detach().insertBefore(form);
      $('input[name="parent"]', form).val(parent.attr('id'));
      $('p.cancel:hidden', form).show();
      F.prepare();

    },
    reset: function() {
      form.css('opacity', 1);
      $('.cancel:visible', form).hide();
      $('textarea', form).val('');
      $('input[name="parent"]', form).val('');
      $('#comments-outer').append(form.detach());
      form.insertBefore(preview.detach());
      _submitting = false;
      return false;
    },
    preview: function(callback) {
      preview.hide();
      var data = commentData();

      $.ajax({
         url: '/plog/preview.json',
        data: data,
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
      var data = commentData();
      if (!$.trim(data.comment).length) {
        alert("Please first write something");
        return false;
      }
      if (_submitting) {
        return false;
      }
      _submitting = true;
      form.css('opacity', 0.3);
      $.ajax({
         url: form.attr('action'),
        data: data,
        type: 'POST',
        dataType: 'json',
        success: function(response) {
          var parent;
          if (response.parent) {
            //parent = $('.commenttext:eq(0)', $('#' + response.parent));
            parent = $('#' + response.parent);
          } else {
            parent = $('#comments-outer');
          }
          parent
            .hide()
              .append(response.html)
                .fadeIn(700);
          $('textarea', form).val('');
          F.reset();
        },
        error: function (jqXHR, textStatus, errorThrown) {
          form.css('opacity', 1);
          alert('Error: ' + errorThrown);
          _submitting = false;
        }
      });
      return false;
    }
  }
})();


$(function() {
  var carousel = $('#carousel');
  if (carousel.size()) {
    $(carousel.carousel({
       interval: 10000
    });
    if (location.hash && /#t\d+/.test(location.hash)) {
      var nth = parseInt(location.hash.replace('#t', ''));
      carousel.carousel(nth - 1);
    }
  }

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

  $('#comments button[name="approve"]').click(function() {
    var oid = $(this).data('oid');
    var url = location.href;
    url = url.split('#')[0];
    url = url.split('?')[0];
    url += '/approve/' + $(this).data('oid');
    var button = $(this);
    $.post(url, {csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val()}, function(response) {
      $('.not-approved', '#' + oid).remove();
      button.remove();
    });
    return false;
  });

  $('#comments button[name="delete"]').click(function() {
    var oid = $(this).data('oid');
    var url = location.href;
    url = url.split('#')[0];
    url = url.split('?')[0];
    url += '/delete/' + oid;
    var button = $(this);
    $.post(url, {csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val()}, function(response) {
      $('#' + oid).remove();
      button.remove();
    });
    return false;
  });

});
