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
      csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]', form).val()
    };
  }

  // http://youmightnotneedjquery.com/#fade_in
  function fadeIn(el) {
    if (!el) {
      throw new Error('Element is null');
    }
    el.style.opacity = 0;
    el.style.display = ''; // peterbe added

    var last = +new Date();
    var tick = function() {
      el.style.opacity = +el.style.opacity + (new Date() - last) / 400;
      last = +new Date();

      if (+el.style.opacity < 1) {
        (window.requestAnimationFrame && requestAnimationFrame(tick)) ||
          setTimeout(tick, 16);
      }
    };
    tick();
  }

  return {
    prepare: function(callback) {
      if (preparing) {
        return; // to avoid excessive calls
      }
      preparing = true;

      fetch('/plog/prepare.json')
        .then(function(r) {
          return r.json();
        })
        .then(function(response) {
          $('input[name="csrfmiddlewaretoken"]', form).val(response.csrf_token);

          if (response.name && !$('input[name="name"]', form).val()) {
            $('input[name="name"]', form)
              .attr('placeholder', '')
              .val(response.name);
          } else {
            var name = localStorage.getItem('name');
            if (name) {
              $('input[name="name"]', form)
                .attr('placeholder', '')
                .val(name);
            }
          }
          if (response.email && !$('input[name="email"]', form).val()) {
            $('input[name="email"]', form)
              .attr('placeholder', '')
              .val(response.email);
          } else {
            var email = localStorage.getItem('email');
            if (email) {
              $('input[name="email"]', form)
                .attr('placeholder', '')
                .val(email);
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
      if (parent.length !== 1) {
        throw new Error('Must be exactly 1 parent');
      }
      // form.detach().insertAfter($('p:eq(0)', parent));
      form.detach().insertAfter($('p', parent).eq(0));
      preview.detach().insertBefore(form);
      $('input[name="parent"]', form).val(parent.attr('id'));
      F.prepare();
      $('textarea', form)[0].focus();
    },
    reset: function() {
      form.css('opacity', 1);
      $('textarea', form).val('');
      $('input[name="parent"]', form).val('');
      $('#comments-outer').append(form.detach());
      preview
        .detach()
        .insertBefore(form)
        .hide();
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
      var formData = new FormData();
      for (var key in data) {
        formData.append(key, data[key]);
      }
      fetch('/plog/preview.json', {
        body: formData,
        method: 'POST'
      })
        .then(function(r) {
          if (r.ok) {
            r.json().then(function(response) {
              preview.html(response.html);
              fadeIn(preview[0]);
              callback();
            });
          } else {
            // Should deal with this better
            console.error(r);
          }
        })
        .catch(function(ex) {
          alert('Error: ' + ex);
        });
    },
    submit: function() {
      var data = commentData();
      if (!data.csrfmiddlewaretoken && !reattempted) {
        reattempted = true;
        F.prepare(F.submit);
        return false;
      }
      if (!data.comment.trim().length) {
        return false;
      }
      if (submitting) {
        return false;
      }
      submitting = true;
      if (!$('.dimmer', form).length) {
        // Need to add this to the DOM before we can activate the dimmer.
        $('<div class="ui inverted dimmer">')
          .append(
            $(
              '<div class="ui text loader">Thank you for posting a comment</div>'
            )
          )
          .prependTo(form);
      }
      $('.dimmer', form).addClass('active');

      var formData = new FormData();
      for (var key in data) {
        formData.append(key, data[key]);
      }

      fetch(form.attr('action'), {
        method: 'POST',
        body: formData
      })
        .then(function(r) {
          // console.log('R:', r);
          if (r.ok) {
            return r.json().then(function(response) {
              var parent;
              if (response.parent) {
                parent = $('.comments', '#' + response.parent).eq(1);
                if (!parent.length) {
                  // need to create this container
                  parent = $('<div class="comments">');
                  parent.appendTo('#' + response.parent);
                }
              } else {
                parent = $('#comments-outer');
              }
              // Put a slight delay on these updates so it "feels"
              // slightly more realistic if the POST manages to happen
              // too fast.
              setTimeout(function() {
                parent.hide().append(response.html);
                fadeIn(parent[0]);
                $('textarea', form).val('');
                $('.dimmer', form).removeClass('active');
              }, 500);

              F.reset();
              var $count = $('span.comment-count');
              if ($count.length) {
                var text;
                if (response.comment_count === 1) {
                  text = '1 comment';
                } else {
                  text = response.comment_count + ' comments';
                }
                $count.text(text);
                fadeIn($count[0]);
              }

              // save the name and email if possible
              if (data.name) {
                localStorage.setItem('name', data.name);
              }
              if (data.email) {
                localStorage.setItem('email', data.email);
              }

              // If it's there, let's delete it.
              $('.ui.message.floating.warning').remove();
            });
          } else {
            console.warn(r);
            var msg = 'Error: ' + r.status + ' ' + r.statusText;
            if (r.status >= 500) {
              msg += '\nTry again in one minute.';
            } else if (r.status === 403) {
              F.prepare();
              msg = 'Security cookie expired. Try submitting again.';
            }
            alert(msg);
            $('.dimmer', form).removeClass('active');
            submitting = false;
          }
        })
        .catch(function(ex) {
          console.error(ex);
          $('.dimmer', form).removeClass('active');
          var msg = 'Error: ' + ex.toString();
          alert(msg);
          submitting = false;
        });
      return false;
    }
  };
})();

$(function() {
  'use strict';

  // This JS might be included on all pages. Even those that are
  // not blog posts. Hence this careful if statement on form.length.
  var form = $('form#comment');

  if (!window.fetch) {
    form.html("<h4><i>Your browser doesn't support posting comments.</i></h4>");
    return;
  }

  function preLyricsPostingMessage() {
    if (document.location.pathname.indexOf('/plog/blogitem-040601-1') > -1) {
      if ($('.ui.message.floating.warning').length) return;
      var message = $(
        '<div class="ui message floating warning" style="margin-top:20px;display:block">'
      );
      message.append(
        $('<div class="header">Before your post a comment...</div>')
      );
      message.append(
        $('<p>')
          .append(
            $(
              '<b>Go to <a href="https://songsear.ch/" title="Search for songs by the lyrics">songsear.ch</a> and do your search</b>'
            )
          )
          .append(
            '<span>, then copy the link to the search results together with your comment.</span>'
          )
      );
      message.insertAfter(form);
    }
  }

  // Create a "Reply" link for all existing comments.
  // But only if the post allows comments.
  // if ($('#preview-comment-outer').length) {
  //   $('div.comment a.metadata').each(function() {
  //     var date = $(this);
  //     var reply = $('<a class="metadata reply" rel="nofollow">Reply</a>');
  //     var oid = date.attr('href').split('#')[1];
  //     reply.attr('href', '#' + oid);
  //     reply.data('oid', oid);
  //     reply.insertAfter(date);
  //   });
  // }
  if (form.length) {
    form.on('mouseover', function() {
      $(this).off('mouseover');
      F.prepare();
      preLyricsPostingMessage();
    });

    $('textarea', form).on('focus', function() {
      $(this).off('focus');
      preLyricsPostingMessage();
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
      var parentOid = $(this)
        .parent()
        .attr('id');
      F.setupReply($('#' + parentOid));
      return false;
    });

    form.on('submit', F.submit);
  }

  var commentsOuter = $('#comments-outer');

  if (commentsOuter.length) {
    var loadingAllComments = false; // for the slow-load lock
    $('.comments-truncated').on('click', 'button', function() {
      if (loadingAllComments) return;
      loadingAllComments = true;

      if (!$('.comments-truncated .dimmer').length) {
        // Inject it into the DOM now
        $('<div class="ui inverted dimmer">')
          .append(
            $(
              '<div class="ui text loader">Loading all the other comments</div>'
            )
          )
          .prependTo($('.comments-truncated'));
      }
      $('.comments-truncated .dimmer').addClass('active');
      commentsOuter.load(location.pathname + '/all-comments', function() {
        $('.comments-truncated').remove();
      });
    });
  }
});
