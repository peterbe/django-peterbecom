PIPELINE_CSS = {
    'base': {
        'source_filenames': (
            # 'css/semantic.css',
            'css/semantic/reset.css',
            'css/semantic/site.css',
            'css/semantic/button.css',
            'css/semantic/container.css',
            'css/semantic/divider.css',
            'css/semantic/header.css',
            # 'css/semantic/icon.css',
            # 'css/semantic/image.css',
            'css/semantic/input.css',
            'css/semantic/label.css',
            'css/semantic/list.css',
            'css/semantic/loader.css',
            'css/semantic/segment.css',
            # 'css/semantic/breadcrumb.css',
            'css/semantic/form.css',
            'css/semantic/grid.css',
            'css/semantic/menu.css',
            'css/semantic/message.css',
            'css/semantic/table.css',
            'css/semantic/item.css',
            'css/semantic/comment.css',
            'css/semantic/dimmer.css',
            'css/semantic/dropdown.css',
            'css/semantic/search.css',

            'css/highlight.css',
            'css/peterbe.css',
            'css/plog-awspa.css',
            'css/carbon-ads.css',
            'css/carbon-campaign.css',
            'autocompeter/autocompeter.min.css',
        ),
        'output_filename': 'css/base.min.css',
    },
    'homepage:search': {
        'source_filenames': (
            # 'css/label.css',
            'css/peterbe-search.css',
        ),
        'output_filename': 'css/search.min.css',
    },

}


PIPELINE_JS = {
    'base': {
        'source_filenames': (
            'libs/jquery-3.3.1.min.js',
            'js/prefetcher.js',
            'js/site.js',
            'js/blogitem.js',
        ),
        'output_filename': 'js/base.min.js',
        'extra_context': {
            'defer': True,
        },
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
    'cssrelpreload': {
        'source_filenames': (
            'js/cssrelpreload.js',
        ),
        'output_filename': 'js/cssrelpreload.min.js',
        'extra_context': {
            'async': True,
        },
    },
    'warmup_songsearch': {
        'source_filenames': (
            'plog/js/warmup-songsearch.js',
        ),
        'output_filename': 'js/warmup-songsearch.min.js',
        'extra_context': {
            'defer': True,
        },
    },
    'autocompeter': {
        'source_filenames': (
            'js/autocompeter.js',
        ),
        'output_filename': 'js/autocompeter.min.js',
        'extra_context': {
            'defer': True,
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
    'plog:post': {
        'source_filenames': (
            'js/blogitem-ping.js',
            'js/blogitem-awspa.js',
        ),
        'output_filename': 'js/blogitem-post.min.js',
        'extra_context': {
            'defer': True,
        },
    },
    'calendar': {
        'source_filenames': (
            'plog/js/calendar.js',
        ),
        'output_filename': 'js/calendar.min.js',
    },
    'new_comments': {
        'source_filenames': (
            'plog/js/new-comments.js',
        ),
        'output_filename': 'js/new-comments.min.js',
        'extra_context': {
            'defer': True,
        },
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
