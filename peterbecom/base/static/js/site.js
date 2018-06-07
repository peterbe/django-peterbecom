/*global $*/
$(function() {
  'use strict';

  // show dropdown on hover
  // $('.main.menu .ui.dropdown').dropdown({
  //   on: 'hover',
  // });

  $('div.ui.dropdown')
    .on('mouseover', function() {
      $(this)
        .addClass('active')
        .addClass('visible');
      $('div.menu', this)
        .removeClass('hidden')
        .addClass('transition')
        .addClass('left')
        .addClass('visible')
        .css('display', 'flex !important');
    })
    .on('mouseout', function() {
      $(this)
        .removeClass('active')
        .removeClass('visible');
      $('div.menu', this)
        .removeClass('visible')
        .addClass('hidden')
        .css('display', 'block');
    });

  function replaceLazyImages() {
    $('div.post img[data-originalsrc]').each(function() {
      var $img = $(this);
      $img.attr('src', $img.data('originalsrc'));
      $img.removeData('originalsrc');
    });
  }

  $(window).on('scroll', function(event) {
    $(window).off('scroll');
    replaceLazyImages();
  });
});
