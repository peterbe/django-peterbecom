$(function() {
  var products = $('form[method="post"]').data('products');
  $('.items').on('click', '.item .extra div.button', function() {
    // console.log('Products', products);
    var button = $(this);
    // console.log(button);
    // console.log(button.parent());
    // console.log(button.parent().parent());
    var item = button
      .parent()
      .parent()
      .parent();
    // console.log('Item', item);
    var id = item.data('id');
    // console.log('Toggle', id, typeof id);
    var button = $('.extra .button', item);
    button.toggleClass('primary');
    if (products.includes(id)) {
      products = products.filter(function(oldId) {
        return oldId !== id;
      })
      button.text('Pick');
    } else {
      products.push(id);
      button.text('Picked');
    }
    var data = {}
    data.products = products;
    data.csrfmiddlewaretoken = $('input[name="csrfmiddlewaretoken"]').val();
    var serializedObj = $.param(data, true);
    $.post(document.location.pathname, serializedObj)
    .done(function(response) {
      // console.log('Saved', response);
    })
    .fail(function(error) {
      throw new Error(error)
    })
  });

  $('button.loadmore').on('click', function() {
    var button = $(this);
    var container = $('.items', button.parent());
    var keyword = button.data('keyword');
    button.addClass('loading');
    $.get('/awspa/search/new', { keyword: keyword, searchindex: 'Books' })
      .done(function(response) {
        if (response.error) {
          alert(`${response.error.Message}\n${response.error.Code}`);
          return;
        }
        console.log(`${response.cards.length} found`);
        $.each(response.cards, function(i, card) {
          container.append(card);
        });
        $('.item', container).each(function() {
          var id = $(this).data('id');
          var button = $('.extra .button', this);
          if (products.includes(id)) {
            button.addClass('primary');
            button.text('Picked');
          }
        });
      })
      .fail(function(error) {
        console.error(error);
      })
      .always(function() {
        button.removeClass('loading');
        // alert( "finished" );
      });
  });
});
