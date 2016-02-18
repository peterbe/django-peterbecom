$(function() {
  function formatRepo (repo) {
    if (repo.loading) return repo.name;

    var markup = "<div class='select2-result-repository clearfix'>" +
      "<div class='select2-result-repository__avatar'><img src='" + repo.image_url + "' /></div>" +
      "<div class='select2-result-repository__meta'>" +
        "<div class='select2-result-repository__title'>" + repo.name + "</div>";

    // if (repo.description) {
    markup += "<div class='select2-result-repository__description'>";
    markup += repo.episodes + " episodes";
    if (repo.hours !== null) {
      markup += ", " + repo.hours.toFixed(1) + " total hours."
    }

    markup += "</div>";
    // }
    markup += "</div></div>";
    // markup += "<div class='select2-result-repository__statistics'>" +
    //   "<div class='select2-result-repository__forks'><i class='fa fa-flash'></i> " + repo.forks_count + " Forks</div>" +
    //   "<div class='select2-result-repository__stargazers'><i class='fa fa-star'></i> " + repo.stargazers_count + " Stars</div>" +
    //   "<div class='select2-result-repository__watchers'><i class='fa fa-eye'></i> " + repo.watchers_count + " Watchers</div>" +
    // "</div>" +
    // "</div></div>";
    return markup;
  }

  function formatRepoSelection(item) {
    console.log('selection:', item);
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
          page: params.page
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
      cache: true
    },
    escapeMarkup: function (markup) { return markup; }, // let our custom formatter work
    minimumInputLength: 1,
    templateResult: formatRepo, // omitted for brevity, see the source of this page
    templateSelection: formatRepoSelection // omitted for brevity, see the source of this page
  });
});
