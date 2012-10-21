$(function() {
  $('.projects .project').each(function() {
    var h3 = $('h3', this);
    h3.append($('<a href="#">')
              .attr('href', '#' + $(this).attr('id'))
              .attr('title', "Link to '" + h3.text() + "'")
              .addClass('perm')
              .text('#'));
  });
});
