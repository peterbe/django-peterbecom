$(function() {

  var formatNumber = function(number) {
    return number.toLocaleString(undefined, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1
    });
  };

  var formatPerDuration = function(hours, container) {
    var value = hours;
    if (value > 2.0) {
      $('.minutes', container).hide();
      $('.hours', container).show(200);
    } else {
      value *= 60;
      $('.hours', container).hide();
      $('.minutes', container).show(200);
    }
    $('.value', container).text(formatNumber(value));
  };

  var fetchStats = function() {
    return $.getJSON('/podcasttime/stats?ids=' + podcastIDs.join(','))
    .done(function(results) {
      var container = $('.selected .stats');

      // The numbers that come back are HOURS per day/week/month.
      // We have to decide to use hours or minutes based on the number.
      formatPerDuration(results.per_day, $('.per-day', container));
      formatPerDuration(results.per_week, $('.per-week', container));
      formatPerDuration(results.per_month, $('.per-month', container));
      container.fadeIn(500);
      return results;
    });
  };

  var updatePicked = function() {
    return $.post('/podcasttime/picked', {
      csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val(),
      ids: podcastIDs.join(',')
    });
  };

  var resetPicked = function() {
    return $.post('/podcasttime/picked', {
      csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val(),
      reset: true,
    });
  };

  // Suppose that you picked a bunch last time,
  // and you refresh the page. Then let's start over on the picked
  // bunches.
  resetPicked();

  var calendar = null;

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
      if (!podcastIDs.length) {
        selection.hide();
        resetPicked();
      } else {
        fetchStats().done(updatePicked);
        calendar.fullCalendar('refetchEvents');
      }
    });
    $('.selected .your-podcasts').prepend(tmpl);

    // right away
    fetchStats().done(updatePicked);

    selection.show();

    if (calendar === null) {
      calendar = $('.calendar').fullCalendar({
        header: {
          left: 'title',
          center: 'prev,next today',
          right: 'month,agendaWeek,agendaDay'
        },
        events: {
          url: '/podcasttime/calendar',
          data: function() {
            return {ids: podcastIDs.join(',')};
          }
        }
      });
    } else {
      calendar.fullCalendar('refetchEvents');
      // console.log('Need to update', calendar);
    }
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
    resetPicked();
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
