$(function() {
  $('form.ui.search').on('submit', function() {
    $('.ui.input', this).addClass('loading');
  });
});
