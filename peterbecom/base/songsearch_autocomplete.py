import filecmp
import os
import re
import shutil
import tempfile
import time
import zipfile
from glob import glob
from pathlib import Path

from django.conf import settings

from peterbecom.mincss_response import has_been_css_minified
from peterbecom.brotli_file import brotli_file
from peterbecom.zopfli_file import zopfli_file

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


def patient_isfile_check(fp, sleep=5, max_attempts=5, impatient=False):
    attempts = 0
    while True:
        if not os.path.isfile(fp):
            if attempts > max_attempts:
                raise SongsearchAutocompleteError(
                    "The file {} does not exist".format(fp)
                )
            attempts += 1
            print("{} did not exist. Sleeping and trying again later...".format(fp))
            time.sleep(sleep)
            continue
        break


def insert(dry_run=False, impatient=False, page=1, legacy=None):
    """Primary function."""

    # There are two folders that we can draw from, the old React based (legacy)
    # or the new Preact one.

    # XXX As of July 2019, let's play it safe and use the legacy one on the
    # home page and the Preact one on the other pages.
    if legacy is None:
        legacy = page == 1

    if legacy:
        # Unzip and zopfli if the content has changed.
        autocompleteroot = settings.BASE_DIR / "songsearch-autocomplete"
        contentroot = settings.BASE_DIR / "peterbecom-static-content"
        assert autocompleteroot.is_dir()
        zip_path = autocompleteroot / "songsearch-autocomplete.zip"
        assert zip_path.is_file(), zip_path
        with tempfile.TemporaryDirectory() as tmpdir:
            # Need str() because Python 3.5
            with open(str(zip_path), "rb") as f:
                zf = zipfile.ZipFile(f)
                zf.extractall(tmpdir)
            tmppath = Path(tmpdir)
            assert list(tmppath.iterdir())
            source = tmppath / "songsearch-autocomplete"
            assert source.is_dir(), source
            destination = contentroot / "songsearch-autocomplete"
            # print(os.listdir(destination + "/js"))
            different = not _are_dir_trees_equal(str(source), str(destination))
            if different:
                shutil.rmtree(str(destination))
                shutil.move(str(source), str(destination))
                print("MOVED {} TO {}".format(source, destination))

        assert contentroot.is_dir()
        csspath, = glob(str(contentroot / "songsearch-autocomplete/css/*.css"))
        jspaths = glob(str(contentroot / "songsearch-autocomplete/js/*.js"))
        jspaths = [x.replace("{}/".format(contentroot), "") for x in jspaths]

        with open(csspath) as f:
            csspayload = f.read()
        csspayload = re.sub(r"\/\*# sourceMappingURL=.*?\*\/", "", csspayload)
        csspayload = csspayload.strip()

        js_block = "\n".join(
            [
                (JS_BLOCK.replace("{cdn}", CDN).replace("{jspath}", jspath)).strip()
                for jspath in jspaths
            ]
        )
        css_block = (
            CSS_BLOCK.replace("{cdn}", CDN).replace("{csspayload}", csspayload)
        ).strip()
    else:

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

        csspath, = [x for x in glob(str(autocompleteroot / "*.css")) if in_template(x)]
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


def _post_process_template(template, impatient, js_block, css_block, dry_run=False):
    if not template.is_file():
        print("WARNING! {} does not exist".format(template))
        return
    assert template.is_file(), template
    # more convenient this way. Also, mostly due to Python 3.5 and legacy
    template = str(template)
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
        raise CSSMinifiedCheckError("Template with problem: {}".format(template))

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
            "</body>", "{}\n{}\n{}\n</body>".format(js_header, js_block, js_footer)
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
            "</head>", "{}\n{}\n{}\n</head>".format(css_header, css_block, css_footer)
        )

    # # Paranoia, because it has happened in the past
    # js_files = re.findall(
    #     r"/songsearch-autocomplete/js/main.[a-f0-9]{8}.chunk.js", content
    # )
    # if len(js_files) != 1:
    #     os.remove(template)
    #     raise SongsearchAutocompleteError(
    #         "Incorrect number of js paths! Should have been just one, not: "
    #         "{}".format(js_files)
    #     )

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

    if original_content != content:
        if dry_run:
            print("DRY RUN! ...BUT WILL WRITE NEW CONTENT TO FILE")
        else:
            with open(template, "w") as f:
                f.write(content)
            if os.path.isfile(template + ".gz"):
                os.remove(template + ".gz")
            _zopfli(template)
            if os.path.isfile(template + ".br"):
                os.remove(template + ".gz")
            _brotli(template)
        print("Updated {} with new content.".format(template))
    else:
        print("Nothing changed in the content. No write.")
        if not os.path.isfile(template + ".gz"):
            print("Going to zopfli a new index.html")
            _zopfli(template)
        if not os.path.isfile(template + ".br"):
            print("Going to brotli a new index.html")
            _brotli(template)

    # XXX Commented out because now the index.html's mtime gets automatically
    # updated sometimes.
    # # The zopfli file should always be younger than the not-zopflied file.
    # age_html = os.stat(template).st_mtime
    # if os.path.isfile(template + ".gz"):
    #     age_gz = os.stat(template + ".gz").st_mtime
    #     if age_html > age_gz:
    #         os.remove(template + ".gz")
    #         raise SongsearchAutocompleteError(
    #             "The index.html.gz file was older than the index.html file"
    #         )
    # if os.path.isfile(template + ".br"):
    #     age_br = os.stat(template + ".br").st_mtime
    #     if age_html > age_br:
    #         os.remove(template + ".br")
    #         raise SongsearchAutocompleteError(
    #             "The index.html.br file was older than the index.html file"
    #         )


def _zopfli(filepath):
    while True:
        original_ts = os.stat(filepath).st_mtime
        original_size = os.stat(filepath).st_size
        t0 = time.time()
        # XXX What happens if you run two threads
        # 1. thread1 starts `zopfli_file(path)`
        # 2. thread2 deletes `path` whilst thread1 is running
        new_filepath = zopfli_file(filepath)
        t1 = time.time()
        if new_filepath:
            print(
                "Generated {} ({} bytes, originally {} bytes) Took {:.2f}s".format(
                    new_filepath,
                    format(os.stat(new_filepath).st_size, ","),
                    format(original_size, ","),
                    t1 - t0,
                )
            )
            if original_ts != os.stat(filepath).st_mtime:
                print(
                    "WARNING! The file {} changed during the "
                    "zopfli process.".format(filepath)
                )
                continue
            break


def _brotli(filepath):
    while True:
        original_ts = os.stat(filepath).st_mtime
        t0 = time.time()
        new_filepath = brotli_file(filepath)
        t1 = time.time()
        if new_filepath:
            print(
                "Generated {} ({} bytes, originally {} bytes) Took {:.2f}s".format(
                    new_filepath,
                    format(os.stat(new_filepath).st_size, ","),
                    format(os.stat(filepath).st_size, ","),
                    t1 - t0,
                )
            )
            if original_ts != os.stat(filepath).st_mtime:
                print(
                    "WARNING! The file {} changed during the "
                    "brotli process.".format(filepath)
                )
                continue
            break
