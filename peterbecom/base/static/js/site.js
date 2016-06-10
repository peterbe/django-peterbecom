/*global $*/
$(function() {
  'use strict';

  // fix main menu to page on passing
  $('.main.menu').visibility({
    type: 'fixed',
  });

  // show dropdown on hover
  $('.main.menu .ui.dropdown').dropdown({
    on: 'hover',
  });

  $('a.page-title-repeated').on('click', function() {
    window.scrollTo(0, 0);
    return false;
  });

  // First decide which blog posts to "collapse"
  $('div.post').each(function(i) {
    if (i < 3 && document.location.search.search(/page=/) === -1) {
      // First of all, don't bother with the first 3 that are likely
      // to be within reach of the first page scrolling.
      // However, this rule only applies if you're on page 1 of the
      // home page.
      return;
    }
    var element = $(this);
    var height = element.height();
    if (height < 600) { // XXX is this a good number?
      // don't bother with the small ones
      return;
    }
    element.data('height', height);
    element.addClass('snippet');
    $('<p>')
      .addClass('read-more')
      .append(
        $('<a>')
          .attr('href', $('h2 a', element).attr('href'))
          .addClass('ui').addClass('button').addClass('primary')
          .text('Read the rest of the blog post')
      )
      .appendTo(element);
  });

  // copied and chopped from https://css-tricks.com/text-fade-read-more/
  $('div.post.snippet .read-more a.button').on('click', function(event) {
    event.preventDefault();
    var $el = $(this);
    var $post = $el.parents('div.post.snippet');
    var $readmore = $el.parent();

    var currentHeight = $post.height();
    var originalHeight = $post.data('height');

    $post
      .css({
        // Set height to prevent instant jumpdown when max height is removed
        'height': currentHeight,
        'max-height': 9999,
      })
      .animate({
        // Add a little 16px margin since that's excluded in the height
        // but something the last <p> tag's margin normally adds
        'height': originalHeight + 16,
      });

    // fade out read-more
    $readmore.fadeOut(400, function() {
      // now we can remove height stuff and the snippet class
      $post
        .removeClass('snippet');
    });

  });

});
