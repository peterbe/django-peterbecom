$(function() {

  var selection = $('.selected');
  var podcastIDs = [];
  function addSelectedPodcast(podcast) {
    podcastIDs.push(podcast.id);
    var domID = 'podcast-' + podcast.id;
    var tmpl = $('.template', selection).clone();
    tmpl.addClass('podcast').removeClass('template').attr('id', domID);
    $('h3', tmpl).text(podcast.name);
    $('img', tmpl).attr('src', podcast.image_url);
    var text = podcast.episodes + ' episodes';
    if (podcast.hours !== null) {
      text += ', about ' + parseInt(podcast.hours, 10) + ' hours';
    }
    $('p', tmpl).text(text);
    $('button', tmpl).on('click', function() {
      $('#' + domID).remove();
      podcastIDs.splice(podcastIDs.indexOf(podcast.id), 1);
      if (!$('.podcast', selection).length) {
        selection.hide();
      }
    });
    $('.selected .your-podcasts').prepend(tmpl);
    selection.show();
  }

  function formatPodcast(podcast) {
    if (podcast.loading) return podcast.name;

    var image_url = podcast.image_url;
    if (image_url === null) {
      image_url = '/static/podcasttime/images/no-image.png';
    }
    var markup = "<div class='select2-result-podcast clearfix'>" +
      "<div class='select2-result-podcast__avatar'><img src='" + image_url + "' /></div>" +
      "<div class='select2-result-podcast__meta'>" +
        "<div class='select2-result-podcast__title'>" + podcast.name + "</div>";
    markup += "<div class='select2-result-podcast__description'>";
    markup += podcast.episodes + " episodes";
    if (podcast.hours !== null) {
      markup += ", about " + parseInt(podcast.hours, 10) + " total hours.";
    }
    markup += "</div>";
    markup += "</div></div>";
    return markup;
  }

  selection.on('click', 'button.remove-all', function() {
    $('.podcast', selection).remove();
    podcastIDs = [];
    selection.hide();
  });

  function formatPodcastSelection(item) {
    return item.name || item.text;
  }

  $('select[name="name"]').select2({
    ajax: {
      url: "/podcasttime/find",
      dataType: 'json',
      delay: 150,
      data: function (params) {
        return {
          q: params.term, // search term
          page: params.page,
        };
      },
      processResults: function (data, params) {
        // parse the results into the format expected by Select2
        // since we are using custom formatting functions we do not need to
        // alter the remote JSON data, except to indicate that infinite
        // scrolling can be used
        params.page = params.page || 1;

        return {
          results: data.items,
          pagination: {
            more: (params.page * 30) < data.total_count
          }
        };
      },
      cache: true,
    },
    escapeMarkup: function (markup) {
      // console.log('Markup', markup);
      return markup; // let our custom formatter work
    },
    minimumInputLength: 1,
    templateResult: formatPodcast,
    templateSelection: formatPodcastSelection,
  })
  .on("select2:select", function (event) {
    addSelectedPodcast(event.params.data);
  });
});
