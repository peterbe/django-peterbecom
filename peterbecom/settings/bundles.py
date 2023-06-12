PIPELINE_CSS = {
    "base": {
        "source_filenames": (
            "css/semantic/reset.min.css",
            "css/semantic/site.min.css",
            # "css/semantic/button.css",
            "css/slim-semantic-button.css",  # My own!
            "css/semantic/container.min.css",
            # "css/semantic/divider.css",
            "css/semantic/header.min.css",
            "css/semantic/input.css",  # has custom hacks
            # "css/semantic/label.css",
            "css/semantic/list.min.css",
            "css/semantic/loader.min.css",
            "css/semantic/segment.min.css",
            "css/semantic/form.min.css",
            # "css/semantic/grid.css",
            "css/slim-semantic-grid.css",
            "css/semantic/menu.min.css",
            "css/semantic/message.min.css",
            "css/semantic/table.min.css",
            "css/semantic/item.min.css",
            "css/semantic/comment.min.css",
            "css/semantic/dimmer.min.css",
            "css/semantic/dropdown.min.css",
            "css/semantic/search.css",
            "css/highlight.css",
            "css/peterbe.css",
            "css/carbon-ads.css",
            # "css/carbon-campaign.css",
            "autocompeter/autocompeter.min.css",
        ),
        "output_filename": "css/base.min.css",
    },
    "lyrics": {
        "source_filenames": (
            "css/semantic/reset.min.css",
            "css/semantic/site.min.css",
            # "css/semantic/button.css",
            "css/slim-semantic-button.css",  # My own!
            "css/semantic/container.min.css",
            # "css/semantic/header.min.css",
            "css/slim-header.css",
            "css/semantic/input.css",
            "css/semantic/loader.min.css",
            # "css/semantic/form.min.css",
            "css/slim-form.css",
            # "css/semantic/grid.css",
            "css/slim-semantic-grid.css",
            "css/semantic/message.min.css",
            "css/semantic/comment.min.css",
            "css/semantic/dimmer.min.css",
            "css/peterbe.css",
            "css/lyrics.css",
            "css/carbon-ads.css",
            # "css/carbon-campaign.css",
        ),
        "output_filename": "css/lyrics.min.css",
    },
    "homepage:search": {
        "source_filenames": (
            # 'css/label.css',
            "css/peterbe-search.css",
        ),
        "output_filename": "css/search.min.css",
    },
}


PIPELINE_JS = {
    "base": {
        "source_filenames": ("libs/cash-8.1.0.min.js", "js/site.js", "js/blogitem.js"),
        "output_filename": "js/base.min.js",
        "extra_context": {"defer": True},
        "template_name": "custom_pipeline/js.html",
    },
    "prefetcher": {
        "source_filenames": ("js/prefetcher.js",),
        "output_filename": "js/prefetcher.min.js",
        "extra_context": {"defer": True},
        "template_name": "custom_pipeline/js-module.html",
    },
    "lyrics": {
        "source_filenames": ("libs/cash-8.1.0.min.js", "js/blogitem.js"),
        "output_filename": "js/lyrics.min.js",
        "extra_context": {"defer": True},
        "template_name": "custom_pipeline/js.html",
    },
    "delayedcss": {
        "source_filenames": ("js/delayedcss.js",),
        "output_filename": "js/delayedcss.min.js",
        "extra_context": {"defer": True},
        "template_name": "custom_pipeline/js.html",
    },
    "carbonnative": {
        "source_filenames": ("js/carbonnative.js",),
        "output_filename": "js/carbonnative.min.js",
        "extra_context": {"async": True},
        "template_name": "custom_pipeline/js.html",
    },
    "autocompeter": {
        "source_filenames": ("js/autocompeter.js",),
        "output_filename": "js/autocompeter.min.js",
        "extra_context": {"defer": True},
        "template_name": "custom_pipeline/js.html",
    },
    "about": {
        "source_filenames": ("js/about.js",),
        "output_filename": "js/about.min.js",
        "extra_context": {"defer": True},
        "template_name": "custom_pipeline/js.html",
    },
    "plog:post": {
        "source_filenames": ("js/blogitem-ping.js",),
        "output_filename": "js/blogitem-post.min.js",
        "extra_context": {"defer": True},
        "template_name": "custom_pipeline/js.html",
    },
    "calendar": {
        "source_filenames": ("plog/js/calendar.js",),
        "output_filename": "js/calendar.min.js",
        "template_name": "custom_pipeline/js.html",
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
        if k == "lyrics":
            # That bundle is very exceptional.
            # Basically, the "base" bundle isn't used in base.html.
            continue
        assert isinstance(k, str), k
        out = v["output_filename"]
        assert isinstance(v["source_filenames"], tuple), v
        assert isinstance(out, str), v
        assert not out.split("/")[-1].startswith("."), k
        assert "_" not in out
        assert out.endswith(".min.css") or out.endswith(".min.js")
        for asset_file in v["source_filenames"]:
            if asset_file in _used:
                # Consider using warnings.warn here instead
                print(
                    "{:<52} in {:<20} already in {}".format(
                        asset_file, k, _used[asset_file]
                    )
                )
                _trouble.add(asset_file)
            _used[asset_file] = k

    for asset_file in _trouble:
        print("REPEATED", asset_file)
        found_in = []
        sets = []
        for k, v in config.items():
            if asset_file in v["source_filenames"]:
                found_in.append(k)
                sets.append(set(list(v["source_filenames"])))
        print("FOUND IN", found_in)
        print("ALWAYS TOGETHER WITH", set.intersection(*sets))
        break
