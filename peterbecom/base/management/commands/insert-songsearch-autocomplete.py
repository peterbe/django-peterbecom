import os
import re
import shutil
import tempfile
import time
import zipfile
from filecmp import dircmp
from glob import glob

from django.conf import settings
from django.core.management.base import BaseCommand

from peterbecom.zopfli_file import zopfli_file

CDN = os.environ.get("CDN", "")

BLOCK = """
<style>{csspayload}</style>
<script src="{cdn}/{jspath}" defer></script>
"""


class SongsearchAutocompleteError(Exception):
    """Something terrible happened."""


def count_diff_files(dcmp):
    differences = 0
    for name in dcmp.diff_files:
        print("diff_file %s found in %s and %s" % (name, dcmp.left, dcmp.right))
        differences += 1
    for sub_dcmp in dcmp.subdirs.values():
        differences += count_diff_files(sub_dcmp)
    return differences


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
            # print(os.listdir(tmpdir))
            assert os.listdir(tmpdir)
            source = os.path.join(tmpdir, "songsearch-autocomplete")
            assert os.path.isdir(source), source
            destination = os.path.join(contentroot, "songsearch-autocomplete")
            dcmp = dircmp(source, destination)
            differences = count_diff_files(dcmp)
            # print("DIFFERENCES", differences)
            if differences:
                shutil.rmtree(destination)
                shutil.move(source, destination)
                print("MOVED", source, "TO", destination)

        assert os.path.isdir(contentroot)
        csspath, = glob(os.path.join(contentroot, "songsearch-autocomplete/css/*.css"))
        jspath, = glob(os.path.join(contentroot, "songsearch-autocomplete/js/*.js"))
        jspath = jspath.replace(contentroot + "/", "")

        with open(csspath) as f:
            csspayload = f.read()
        csspayload = re.sub(r"\/\*# sourceMappingURL=.*?\*\/", "", csspayload)
        csspayload = csspayload.strip()

        block = (
            BLOCK.replace("{cdn}", CDN)
            .replace("{csspayload}", csspayload)
            .replace("{jspath}", jspath)
        )
        block = block.strip()
        template = os.path.join(
            contentroot, "_FSCACHE/plog/blogitem-040601-1/index.html"
        )
        if not os.path.isfile(template):
            raise SongsearchAutocompleteError(
                "The file {} does not exist".format(template)
            )
        with open(template) as f:
            original_content = content = f.read()
        header = "<!-- songsearch-autocomplete -->"
        start = content.find(header)
        footer = "<!-- /songsearch-autocomplete -->"
        end = content.find(footer)
        if start > -1:
            content = content[:start] + header + "\n" + block + "\n" + content[end:]
        else:
            if footer in content and header not in content:
                raise SongsearchAutocompleteError(
                    "Only footer is in the HTML but not the header"
                )
            content = content.replace(
                "</body>", "{}\n{}\n{}\n</body>".format(header, block, footer)
            )

        # Paranoia, because it has happened in the past
        js_files = re.findall(
            r"/songsearch-autocomplete/js/main.[a-f0-9]{8}.js", content
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
