/*global $*/
$(function() {
  'use strict';

  $('div.ui.dropdown').on('click', function() {
    var $this = $(this);
    var $menu = $('div.menu', this);

    if ($this.hasClass('active')) {
      $this.removeClass('active');
      $menu.addClass('hidden');
      $menu.removeClass('visible');
      $menu.css('display', 'none');
    } else {
      $this.addClass('active');
      $menu.removeClass('hidden');
      $menu.addClass('visible');
      $menu.css('display', 'block');
    }
  });

  function replaceLazyImages() {
    $('div.post img[data-originalsrc]').each(function() {
      var $img = $(this);
      $img.attr('src', $img.data('originalsrc'));
      $img.data('originalsrc', null);
    });
  }

  $(window).on('scroll', function() {
    $(window).off('scroll');
    replaceLazyImages();
  });
});
