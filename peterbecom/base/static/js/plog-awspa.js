$(function() {
  $('button.loadmore').on('click', function() {
    var button = $(this);
    var container = $('.items', button.parent());
    var keyword = button.data('keyword');
    $.get('/awspa/search/new', {keyword: keyword, searchindex: 'Books'})
    .done(function(response) {
      console.log(response);
      $.each(response.cards, function(i, card) {
        // console.log('CARD', card);
        container.append(card);
      })
    })
    .fail(function(error) {
      console.error(error);
    })
    .always(function() {
      // alert( "finished" );
    });
  });
});
