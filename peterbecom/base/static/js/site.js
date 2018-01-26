/*global $*/
$(function() {
  'use strict';

  // show dropdown on hover
  $('.main.menu .ui.dropdown').dropdown({
    on: 'hover',
  });

  function replaceLazyImages() {
    $('div.post img[data-originalsrc]').each(function() {
      var $img = $(this);
      $img.attr('src', $img.data('originalsrc'))
      $img.removeData('originalsrc');

    })
  }

  $(window).on('scroll', function(event) {
    $(window).off('scroll');
    replaceLazyImages();
  });

});
