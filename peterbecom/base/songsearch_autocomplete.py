import filecmp
import os
import re
import time
from glob import glob
from pathlib import Path

from django.conf import settings

from peterbecom.mincss_response import has_been_css_minified
from peterbecom.brotli_file import brotli_file
from peterbecom.zopfli_file import zopfli_file
from peterbecom.base.decorators import lock_decorator

CDN = os.environ.get("CDN", "")

CSS_BLOCK = """
<style>{csspayload}</style>
"""

JS_BLOCK = """
<script src="{cdn}/{jspath}" defer></script>
"""

# This idea comes from the
# songsearch-autocomplete-preact/build/index.html template
# that it generates.
JS_BLOCK_WITH_POLYFILL_BLOCK = (
    '<script defer src="{jspath}"></script>'
    "<script>window.fetch||document.write('<script "
    'src="{polyfillpath}"><\\/script>\')</script>'
)


class SongsearchAutocompleteError(Exception):
    """Something terrible happened."""


class CSSMinifiedCheckError(Exception):
    """When there's something wrong with checking the CSS minified."""


def _are_dir_trees_equal(dir1, dir2):
    """
    Compare two directories recursively. Files in each directory are
    assumed to be equal if their names and contents are equal.

    @param dir1: First directory path
    @param dir2: Second directory path

    @return: True if the directory trees are the same and
        there were no errors while accessing the directories or files,
        False otherwise.
    """

    dirs_cmp = filecmp.dircmp(dir1, dir2)
    if (
        len(dirs_cmp.left_only) > 0
        or len(dirs_cmp.right_only) > 0
        or len(dirs_cmp.funny_files) > 0
    ):
        return False
    (_, mismatch, errors) = filecmp.cmpfiles(
        dir1, dir2, dirs_cmp.common_files, shallow=False
    )
    if len(mismatch) > 0 or len(errors) > 0:
        return False
    for common_dir in dirs_cmp.common_dirs:
        new_dir1 = os.path.join(dir1, common_dir)
        new_dir2 = os.path.join(dir2, common_dir)
        if not _are_dir_trees_equal(new_dir1, new_dir2):
            return False
    return True


def patient_isfile_check(fp: Path, sleep=5, max_attempts=5, impatient=False):
    attempts = 0
    while True:
        if not fp.exists():
            if attempts > max_attempts:
                raise SongsearchAutocompleteError(f"The file {fp} does not exist")
            attempts += 1
            print(f"{fp} did not exist. Sleeping and trying again later...")
            time.sleep(sleep)
            continue
        break


def insert(dry_run=False, impatient=False, page=1, legacy=False):
    """Primary function."""
    # There are two folders that we can draw from, the old React based (legacy)
    # or the new Preact one.

    contentroot = settings.BASE_DIR / "peterbecom-static-content"
    autocompleteroot = contentroot / "songsearch-autocomplete-preact"
    assert autocompleteroot.is_dir()
    assert contentroot.is_dir()
    # To know which .css and which .js files to use, we need to read the contents
    # of the index.html generated.
    with open(str(autocompleteroot / "index.html")) as f:
        index_html = f.read()

    def in_template(path):
        return os.path.basename(path) in index_html

    (csspath,) = [x for x in glob(str(autocompleteroot / "*.css")) if in_template(x)]
    jspaths = [x for x in glob(str(autocompleteroot / "*.js")) if in_template(x)]
    jspaths = [x.replace("{}/".format(contentroot), "/") for x in jspaths]

    with open(csspath) as f:
        csspayload = f.read()
    csspayload = re.sub(r"\/\*# sourceMappingURL=.*?\*\/", "", csspayload)
    csspayload = csspayload.strip()

    js_block = JS_BLOCK_WITH_POLYFILL_BLOCK.format(
        jspath=[x for x in jspaths if "polyfill" not in x][0],
        polyfillpath=[x for x in jspaths if "polyfill" in x][0],
    )
    css_block = (
        CSS_BLOCK.replace("{cdn}", CDN).replace("{csspayload}", csspayload)
    ).strip()

    if page > 1:
        template = (
            contentroot / "_FSCACHE/plog/blogitem-040601-1/p{}/index.html".format(page)
        )
    else:
        template = contentroot / "_FSCACHE/plog/blogitem-040601-1/index.html"
    _post_process_template(template, impatient, js_block, css_block, dry_run=dry_run)


def _post_process_template(
    template: Path, impatient, js_block, css_block, dry_run=False
):
    if not template.is_file():
        print(f"WARNING! {template} does not exist")
        return
    assert template.is_file(), template
    # # more convenient this way. Also, mostly due to Python 3.5 and legacy
    # template = str(template)
    if not impatient:
        patient_isfile_check(template)

    with open(template) as f:
        original_content = content = f.read()

    # The assumption is that the HTML has been CSS minified. Only after that has
    # been done can we insert (or not insert) the autocomplete snippets.
    # The simplest way to check is if there's a `<link rel="preload" href="*.css"`
    # tag and a big blob of <style>
    try:
        if not has_been_css_minified(content):
            print("WARNING! The HTML file hasn't been CSS minified yet.")
            return
    except ValueError:
        raise CSSMinifiedCheckError(f"Template with problem: {template}")

    # Inject the JS code
    js_header = "<!-- songsearch-autocomplete -->"
    start = content.find(js_header)
    js_footer = "<!-- /songsearch-autocomplete -->"
    end = content.find(js_footer)
    if start > -1:
        content = content[:start] + js_header + "\n" + js_block + "\n" + content[end:]
    else:
        if js_footer in content and js_header not in content:
            raise SongsearchAutocompleteError(
                "Only footer is in the HTML but not the header"
            )
        content = content.replace(
            "</head>", f"{js_header}\n{js_block}\n{js_footer}\n</head>"
        )

    # Inject the CSS code
    css_header = "<!-- songsearch-autocomplete-css -->"
    start = content.find(css_header)
    css_footer = "<!-- /songsearch-autocomplete-css -->"
    end = content.find(css_footer)
    if start > -1:
        content = content[:start] + css_header + "\n" + css_block + "\n" + content[end:]
    else:
        if css_footer in content and css_header not in content:
            raise SongsearchAutocompleteError(
                "Only footer is in the HTML but not the header"
            )
        content = content.replace(
            "</head>", f"{css_header}\n{css_block}\n{css_footer}\n</head>"
        )

    # When it's done it should only be exactly 1 of these bits of strings
    # in the HTML (actually, it's inside the <style> tag)
    css_bit = "License for minified and inlined CSS originally belongs to Semantic UI"
    if content.count(css_bit) != 1:
        print(content)
        raise SongsearchAutocompleteError(
            "There is not exactly 1 ({} instead) CSS license strings".format(
                content.count(css_bit)
            )
        )

    gz_template = Path(str(template) + ".gz")
    br_template = Path(str(template) + ".br")

    if original_content != content:
        if dry_run:
            print("DRY RUN! ...BUT WILL WRITE NEW CONTENT TO FILE")
        else:
            with open(template, "w") as f:
                f.write(content)

            if gz_template.exists():
                gz_template.unlink()
            _zopfli(template)

            if br_template.exists():
                br_template.unlink()
            _brotli(template)
        print(f"Updated {template} with new content.")
    else:
        print("Nothing changed in the content. No write.")
        if not gz_template.exists():
            print("Going to zopfli a new index.html")
            _zopfli(template)
        if not br_template.exists():
            print("Going to brotli a new index.html")
            _brotli(template)


# def _zopfli(filepath: Path):
#     while True:
#         original_ts = filepath.stat().st_mtime
#         original_size = filepath.stat().st_size
#         t0 = time.time()
#         # XXX What happens if you run two threads
#         # 1. thread1 starts `zopfli_file(path)`
#         # 2. thread2 deletes `path` whilst thread1 is running
#         new_filepath: Path = zopfli_file(filepath)
#         t1 = time.time()
#         if new_filepath:
#             print(
#                 f"Generated {new_filepath} ({new_filepath.stat().st_size:,} bytes, "
#                 f"originally {original_size:,} bytes) Took {t1 - t0:.2f}s"
#             )
#             if original_ts != filepath.stat().st_mtime:
#                 print(
#                     f"WARNING! The file {filepath} changed during the zopfli process."
#                 )
#                 continue
#             break


@lock_decorator(key_maker=lambda filepath: str(filepath))
def _zopfli(filepath: Path):
    original_ts = filepath.stat().st_mtime
    original_size = filepath.stat().st_size
    t0 = time.perf_counter()
    new_filepath: Path = zopfli_file(filepath)
    t1 = time.perf_counter()
    if new_filepath:
        print(
            f"Generated {new_filepath} ({new_filepath.stat().st_size:,} bytes, "
            f"originally {original_size:,} bytes) Took {t1 - t0:.2f}s"
        )
        if original_ts != filepath.stat().st_mtime:
            print(f"WARNING! The file {filepath} changed during the zopfli process.")
    else:
        print(f"Failed to zopfli the file {filepath}!")


def _brotli(filepath: Path):
    while True:
        original_ts = filepath.stat().st_mtime
        t0 = time.time()
        attempts = 5
        while attempts:
            new_filepath: Path = brotli_file(filepath)
            if new_filepath.exists():
                break
            print(f"WARNING! {new_filepath} doesn't exist. Sleeping...")
            time.sleep(1)
            attempts -= 1

        t1 = time.time()
        if new_filepath:
            print(
                f"Generated {new_filepath} ({new_filepath.stat().st_size:,} bytes, "
                f"originally {filepath.stat().st_size:,} bytes) Took {t1 - t0:.2f}s"
            )
            if original_ts != filepath.stat().st_mtime:
                print(
                    f"WARNING! The file {filepath} changed during the brotli process."
                )
                continue
            break
