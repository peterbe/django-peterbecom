/*global $*/
$(function () {
  'use strict';

  var imagePath = '/avatar.png';
  var img = $('<img src="' + imagePath + '" alt="Avatar">');
  img.appendTo($('#figure'));

  $('button.reload').on('click', function () {
    img.attr('src', imagePath + '?seed=' + Math.random());
  });
});
