/*global $, localStorage, location*/

var F = (function() {
  'use strict';

  var form = $('form#comment');
  var preview = $('#preview-comment-outer');
  var submitting = false;
  var preparing = false;
  var reattempted = false;

  function commentData() {
    if (!$('input[name="csrfmiddlewaretoken"]', form).val()) {
      F.prepare();
    }
    return {
      name: $('input[name="name"]', form).val(),
      email: $('input[name="email"]', form).val(),
      parent: $('input[name="parent"]', form).val(),
      comment: $('textarea', form).val(),
      csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]', form).val(),
    };
  }

  return {
    prepare: function(callback) {
      if (preparing) {
        return;  // to avoid excessive calls
      }
      preparing = true;
      $.getJSON('/plog/prepare.json', function(response) {
        $('input[name="csrfmiddlewaretoken"]', form).val(response.csrf_token);
        if (response.name && !$('input[name="name"]', form).val()) {
          $('input[name="name"]', form).val(response.name);
        } else {
          var name = localStorage.getItem('name');
          if (name) {
            $('input[name="name"]', form).val(name);
          }
        }
        if (response.email && !$('input[name="email"]', form).val()) {
          $('input[name="email"]', form).val(response.email);
        } else {
          var email = localStorage.getItem('email');
          if (email) {
            $('input[name="email"]', form).val(email);
          }
        }

        preparing = false;
        if (callback) {
          callback();
        }
      });
    },
    setupReply: function(parent) {
      preparing = false;
      if (parent.size() !== 1) {
        throw new Error('Must be exactly 1 parent');
      }
      form.detach().insertAfter($('.text:eq(0)', parent));
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
      preview.detach().insertBefore(form).hide();
      $('button.preview').addClass('primary');
      $('button.post').removeClass('primary');
      submitting = false;
      form.detach().insertAfter('#comments-outer');
      return false;
    },
    preview: function(callback) {
      preview.hide();
      var data = commentData();
      if (!data.csrfmiddlewaretoken && !reattempted) {
        reattempted = true;
        F.prepare(F.preview);
        return false;
      }

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
        },
      });
    },
    submit: function() {
      var data = commentData();
      if (!data.csrfmiddlewaretoken && !reattempted) {
        reattempted = true;
        F.prepare(F.submit);
        return false;
      }
      if (!$.trim(data.comment).length) {
        // alert('Please first write something');
        return false;
      }
      if (submitting) {
        return false;
      }
      submitting = true;
      form.css('opacity', 0.3);
      $.ajax({
        url: form.attr('action'),
        data: data,
        type: 'POST',
        dataType: 'json',
        success: function(response) {
          var parent;
          if (response.parent) {
            parent = $('.comments', '#' + response.parent).eq(1);
          } else {
            parent = $('#comments-outer');
          }
          parent
            .hide()
              .append(response.html)
                .fadeIn(700);
          $('textarea', form).val('');
          F.reset();
          $('span.comment-count').fadeOut(600, function() {
            var text;
            if (response.comment_count === 1) {
              text = '1 comment';
            } else {
              text = response.comment_count + ' comments';
            }
            $(this)
              .text(text)
                .fadeIn(1000);
          });
          // save the name and email if possible
          if (data.name) {
            localStorage.setItem('name', data.name);
          }
          if (data.email) {
            localStorage.setItem('email', data.email);
          }
        },
        error: function (jqXHR, textStatus, errorThrown) {
          form.css('opacity', 1);
          alert('Error: ' + errorThrown);
          submitting = false;
        },
      });
      return false;
    },
  };
})();


$(function() {
  'use strict';

  var form = $('form#comment');

  form.on('mouseover', function() {
    $(this).off('mouseover');
    F.prepare();
  });

  form.on('mouseover', function() {
    $(this).off('mouseover');
    F.prepare();
  });

  form.on('click', 'button.preview', function() {
    if ($('textarea', form).val()) {
      F.preview(function() {
        $('button.preview', form).removeClass('primary');
        $('button.post', form).addClass('primary');
      });
    }
    return false;
  });

  $('#comments-outer').on('click', 'a.reply', function() {
    F.setupReply($('#' + $(this).attr('data-oid')));
    return false;
  });

  form.on('submit', F.submit);

  form.on('click', '.cancel a', F.reset);

  $('#comments-outer').on('click', 'button[name="approve"]', function() {
    var oid = $(this).data('oid');
    var url = location.href;
    url = url.split('#')[0];
    url = url.split('?')[0];
    url += '/approve/' + $(this).data('oid');
    var button = $(this);
    $.post(url, {csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val()}, function() {
      $('.not-approved', '#' + oid).remove();
      button.remove();
    });
    return false;
  });

  $('#comments-outer').on('click', 'button[name="delete"]', function() {
    var oid = $(this).data('oid');
    var url = location.pathname;
    url += '/delete/' + oid;
    $.post(url, {csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val()}, function() {
      $('#' + oid).remove();
    });
    return false;
  });

  var loadingAllComments = false;  // for the slow-load lock
  $('.comments-truncated').on('click', 'button', function() {
    if (loadingAllComments) return;
    loadingAllComments = true;
    $('#comments-outer').load(location.pathname + '/all-comments', function() {
      $('.comments-truncated').remove();
    });
  });

});
