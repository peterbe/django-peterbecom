PIPELINE_CSS = {
    'base': {
        'source_filenames': (
            'css/reset.css',
            'css/site.css',
            'css/container.css',
            'css/grid.css',
            'css/header.css',
            'css/image.css',
            'css/menu.css',
            'css/divider.css',
            'css/list.css',
            'css/segment.css',
            'css/dropdown.css',
            'css/icon.css',
            'css/input.css',
            'css/comment.css',
            'css/message.css',
            'css/loader.css',
            'css/form.css',
            'css/button.css',
            'css/highlight.css',
            'css/table.css',
            'css/peterbe.css',
            'css/carbonads.css',
        ),
        'output_filename': 'css/base.min.css',
    },
    'base_dynamic': {
        'source_filenames': (
            'css/dimmer.css',
            'css/transition.css',
            'autocompeter/autocompeter.min.css',
        ),
        'extra_context': {
            'no_mincss': True,
        },
        'output_filename': 'css/base-dynamic.min.css',
    },
    'homepage:search': {
        'source_filenames': (
            'css/label.css',
        ),
        'output_filename': 'css/search.min.css',
    },
    # 'podcasttime': {
    #     'source_filenames': (
    #         'podcasttime/select2/css/select2.min.css',
    #         'podcasttime/css/podcasttime.css',
    #         'css/statistic.css',
    #     ),
    #     'output_filename': 'css/podcasttime.min.css',
    # },
    # 'podcasttime:podcasts': {
    #     'source_filenames': (
    #         'css/card.css',
    #         'css/label.css',
    #         'css/search.css',
    #         'podcasttime/css/podcasts.css',
    #     ),
    #     'output_filename': 'css/podcasttime.podcasts.min.css',
    # },

}


PIPELINE_JS = {
    'base': {
        'source_filenames': (
            'js/jquery-2.2.4.min.js',
            'js/transition.js',
            'js/dropdown.js',
            # 'js/visibility.js',
            'js/prefetcher.js',
            'js/site.js',
        ),
        'output_filename': 'js/base.min.js',
    },
    'google_analytics': {
        'source_filenames': (
            'js/google-analytics.js',
        ),
        'output_filename': 'js/google-analytics.min.js',
        'extra_context': {
            'async': True,
        },
    },
    'warmup_songsearch': {
        'source_filenames': (
            'plog/js/warmup-songsearchxxx.js',
        ),
        'output_filename': 'js/warmup-songsearch.min.js',
    },
    'autocompeter': {
        'source_filenames': (
            'js/autocompeter.js',
        ),
        'output_filename': 'js/autocompeter.min.js',
        'extra_context': {
            'async': True,
        },
    },
    'about': {
        'source_filenames': (
            'js/about.js',
        ),
        'output_filename': 'js/about.min.js',
        'extra_context': {
            'defer': True,
        },
    },
    'blogitem': {
        'source_filenames': (
            'js/blogitem.js',
        ),
        'output_filename': 'js/blogitem.min.js',
    },
    'plog:ping': {
        'source_filenames': (
            'js/blogitem-ping.js',
        ),
        'output_filename': 'js/blogitem-ping.min.js',
        'extra_context': {
            'async': True,
        },
    },
    'calendar': {
        'source_filenames': (
            'plog/js/calendar.js',
        ),
        'output_filename': 'js/calendar.min.js',
    },
}


# This is sanity checks, primarily for developers. It checks that
# you haven't haven't accidentally make a string a tuple with an
# excess comma, no underscores in the bundle name and that the
# bundle file extension is either .js or .css.
# We also check, but only warn, if a file is re-used in a different bundle.
# That's because you might want to consider not including that file in the
# bundle and instead break it out so it can be re-used on its own.
_used = {}
for config in PIPELINE_JS, PIPELINE_CSS:  # NOQA
    _trouble = set()
    for k, v in config.items():
        assert isinstance(k, str), k
        out = v['output_filename']
        assert isinstance(v['source_filenames'], tuple), v
        assert isinstance(out, str), v
        assert not out.split('/')[-1].startswith('.'), k
        assert '_' not in out
        assert out.endswith('.min.css') or out.endswith('.min.js')
        for asset_file in v['source_filenames']:
            if asset_file in _used:
                # Consider using warnings.warn here instead
                print('{:<52} in {:<20} already in {}'.format(
                    asset_file,
                    k,
                    _used[asset_file]
                ))
                _trouble.add(asset_file)
            _used[asset_file] = k

    for asset_file in _trouble:
        print("REPEATED", asset_file)
        found_in = []
        sets = []
        for k, v in config.items():
            if asset_file in v['source_filenames']:
                found_in.append(k)
                sets.append(set(list(v['source_filenames'])))
        print("FOUND IN", found_in)
        print("ALWAYS TOGETHER WITH", set.intersection(*sets))
        break
