/*global $*/
$(function() {
  'use strict';

  // fix main menu to page on passing
  $('.main.menu').visibility({
    type: 'fixed'
  });

  // show dropdown on hover
  $('.main.menu  .ui.dropdown').dropdown({
    on: 'hover'
  });

  $('a.page-title-repeated').on('click', function() {
    window.scrollTo(0, 0);
    return false;
  });

});
