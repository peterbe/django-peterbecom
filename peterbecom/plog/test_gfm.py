from peterbecom.plog.gfm import gfm


def test_single_underscores():
    """Don't touch single underscores inside words."""
    assert gfm("foo_bar") == "foo_bar"


def test_underscores_code_blocks():
    """Don't touch underscores in code blocks."""
    assert gfm("    foo_bar_baz") == "    foo_bar_baz"


def test_underscores_pre_blocks():
    """Don't touch underscores in pre blocks."""
    assert gfm("<pre>\nfoo_bar_baz\n</pre>") == "\n\n<pre>\nfoo_bar_baz\n</pre>"


def test_pre_block_pre_text():
    """Don't treat pre blocks with pre-text differently."""
    a = "\n\n<pre>\nthis is `a\\_test` and this\\_too\n</pre>"
    b = "hmm<pre>\nthis is `a\\_test` and this\\_too\n</pre>"
    assert gfm(a)[2:] == gfm(b)[3:]


def test_two_underscores():
    """Escape two or more underscores inside words."""
    assert gfm("foo_bar_baz") == "foo\\_bar\\_baz"


def test_newlines_simple():
    """Turn newlines into br tags in simple cases."""
    assert gfm("foo\nbar") == "foo  \nbar"


def test_newlines_group():
    """Convert newlines in all groups."""
    assert (
        gfm("apple\npear\norange\n\nruby\npython\nerlang")
        == "apple  \npear  \norange\n\nruby  \npython  \nerlang"
    )


def test_newlines_long_group():
    """Convert newlines in even long groups."""
    assert (
        gfm("apple\npear\norange\nbanana\n\nruby\npython\nerlang")
        == "apple  \npear  \norange  \nbanana\n\nruby  \npython  \nerlang"
    )


def test_newlines_list():
    """Don't convert newlines in lists."""
    assert gfm("# foo\n# bar") == "# foo\n# bar"
    assert gfm("* foo\n* bar") == "* foo\n* bar"
