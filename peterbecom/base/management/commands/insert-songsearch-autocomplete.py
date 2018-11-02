import os
import re
import shutil
import tempfile
import time
import zipfile
import filecmp
from glob import glob

from django.conf import settings
from django.core.management.base import BaseCommand

from peterbecom.zopfli_file import zopfli_file

CDN = os.environ.get("CDN", "")

CSS_BLOCK = """
<style>{csspayload}</style>
"""

JS_BLOCK = """
<script src="{cdn}/{jspath}" defer></script>
"""


class SongsearchAutocompleteError(Exception):
    """Something terrible happened."""


# def count_diff_files(dcmp):
#     differences = 0
#     for name in dcmp.diff_files:
#         print("diff_file %s found in %s and %s" % (name, dcmp.left, dcmp.right))
#         differences += 1
#     for sub_dcmp in dcmp.subdirs.values():
#         differences += count_diff_files(sub_dcmp)
#     return differences


def are_dir_trees_equal(dir1, dir2):
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
        if not are_dir_trees_equal(new_dir1, new_dir2):
            return False
    return True


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print instead of deleting",
        )

    def handle(self, **options):
        dry_run = options["dry_run"]

        # Unzip and zopfli if the content has changed.
        autocompleteroot = os.path.join(settings.BASE_DIR, "songsearch-autocomplete")
        contentroot = os.path.join(settings.BASE_DIR, "peterbecom-static-content")
        assert os.path.isdir(autocompleteroot)
        zip_path = os.path.join(autocompleteroot, "songsearch-autocomplete.zip")
        assert os.path.isfile(zip_path)
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(zip_path, "rb") as f:
                zf = zipfile.ZipFile(f)
                zf.extractall(tmpdir)
            # print(os.listdir(tmpdir + "/songsearch-autocomplete/js"))
            assert os.listdir(tmpdir)
            source = os.path.join(tmpdir, "songsearch-autocomplete")
            assert os.path.isdir(source), source
            destination = os.path.join(contentroot, "songsearch-autocomplete")
            # print(os.listdir(destination + "/js"))
            different = not are_dir_trees_equal(source, destination)
            if different:
                shutil.rmtree(destination)
                shutil.move(source, destination)
                print("MOVED", source, "TO", destination)

        assert os.path.isdir(contentroot)
        csspath, = glob(os.path.join(contentroot, "songsearch-autocomplete/css/*.css"))
        jspaths = glob(os.path.join(contentroot, "songsearch-autocomplete/js/*.js"))
        jspaths = [x.replace(contentroot + "/", "") for x in jspaths]

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

        template = os.path.join(
            contentroot, "_FSCACHE/plog/blogitem-040601-1/index.html"
        )
        if not os.path.isfile(template):
            raise SongsearchAutocompleteError(
                "The file {} does not exist".format(template)
            )
        with open(template) as f:
            original_content = content = f.read()

        # Inject the JS code
        js_header = "<!-- songsearch-autocomplete -->"
        start = content.find(js_header)
        js_footer = "<!-- /songsearch-autocomplete -->"
        end = content.find(js_footer)
        if start > -1:
            content = (
                content[:start] + js_header + "\n" + js_block + "\n" + content[end:]
            )
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
            content = (
                content[:start] + css_header + "\n" + css_block + "\n" + content[end:]
            )
        else:
            if css_footer in content and css_header not in content:
                raise SongsearchAutocompleteError(
                    "Only footer is in the HTML but not the header"
                )
            content = content.replace(
                "</head>",
                "{}\n{}\n{}\n</head>".format(css_header, css_block, css_footer),
            )

        # Paranoia, because it has happened in the past
        js_files = re.findall(
            r"/songsearch-autocomplete/js/main.[a-f0-9]{8}.chunk.js", content
        )
        if len(js_files) != 1:
            os.remove(template)
            raise SongsearchAutocompleteError(
                "Incorrect number of js paths! Should have been just one, not: "
                "{}".format(js_files)
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
            print("Updated {} with new content.".format(template))
        else:
            print("Nothing changed in the content. No write.")
            if not os.path.isfile(template + ".gz"):
                print("Going to zopfli a new index.html")
                _zopfli(template)

        # The zopfli file should always be younger than the not-zopflied file.
        age_html = os.stat(template).st_mtime
        age_gz = os.stat(template + ".gz").st_mtime
        if age_html > age_gz:
            os.remove(template + ".gz")
            raise SongsearchAutocompleteError(
                "The index.html.gz file was older than the index.html file"
            )


def _zopfli(filepath):
    while True:
        original_ts = os.stat(filepath).st_mtime
        t0 = time.time()
        new_filepath = zopfli_file(filepath)
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
                    "zopfli process.".format(filepath)
                )
                continue
            break
