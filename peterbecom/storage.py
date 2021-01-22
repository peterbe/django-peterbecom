import os
from io import BytesIO

import brotli
from django.conf import settings
from django.contrib.staticfiles.utils import matches_patterns
from django.core.files.base import File
from pipeline.storage import PipelineManifestStorage
from zopfli import gzip as zopfli


class ZopfliAndBrotliMixin(object):
    name_patterns = ("*.css", "*.js", "*.svg")

    # 'numiterations' default is 15 in
    # https://github.com/obp/py-zopfli/blob/master/src/zopflimodule.c
    numiterations = getattr(settings, "ZOPFLI_COMPRESS_NUM_ITERATIONS", 15)
    minimum_size_bytes = getattr(settings, "ZOPFLI_COMPRESS_MIN_SIZE_BYTES", 256)
    only_hashed_files = getattr(settings, "ZOPFLI_COMPRESS_ONLY_HASHED_FILES", True)

    def _zopfli_compress(self, original_file):
        original_file.seek(0)
        content = BytesIO(
            zopfli.compress(original_file.read(), numiterations=self.numiterations)
        )
        content.seek(0)
        return File(content)

    def _brotli_compress(self, original_file):
        original_file.seek(0)
        content = BytesIO(brotli.compress(original_file.read()))
        content.seek(0)
        return File(content)

    def post_process(self, paths, dry_run=False, **options):
        super_class = super()
        processed_hash_names = []
        if hasattr(super_class, "post_process"):
            for name, hashed_name, processed in super_class.post_process(
                paths.copy(), dry_run, **options
            ):
                # XXX should we continue here if it's a something from node_modules?
                # print((name, hashed_name, processed))
                if hashed_name != name:
                    paths[hashed_name] = (self, hashed_name)
                    processed_hash_names.append(hashed_name)

                yield name, hashed_name, processed

        if dry_run:
            return

        for path in processed_hash_names:
            if not matches_patterns(path, self.name_patterns):
                continue

            original_file = self.open(path)
            if original_file.size < self.minimum_size_bytes:
                continue

            gzipped_path = "{0}.gz".format(path)
            if not self.exists(gzipped_path):
                # This is the beauty of using django_pipeline.
                # If the .gz file exists, it means the source of it hasn't changed
                # even though it was re-written to disk, because we only bother
                # with files with hashed in the name.
                compressed_file = self._zopfli_compress(original_file)
                gzipped_path = self.save(gzipped_path, compressed_file)
                abs_path = os.path.join(settings.STATIC_ROOT, gzipped_path)
                if os.getenv("CI") or os.stat(abs_path).st_size > 1:
                    yield gzipped_path, gzipped_path, True
                else:
                    # Something went very wrong!
                    size_before = os.stat(abs_path).st_size
                    os.remove(abs_path)
                    print(
                        "The file {} was too small! ({} bytes)".format(
                            abs_path, size_before
                        )
                    )

            brotli_path = "{0}.br".format(path)
            if not self.exists(brotli_path):
                # This is the beauty of using django_pipeline.
                # If the .gz file exists, it means the source of it hasn't changed
                # even though it was re-written to disk, because we only bother
                # with files with hashed in the name.
                compressed_file = self._brotli_compress(original_file)
                brotli_path = self.save(brotli_path, compressed_file)
                abs_path = os.path.join(settings.STATIC_ROOT, brotli_path)
                if os.getenv("CI") or os.stat(abs_path).st_size > 1:
                    yield brotli_path, brotli_path, True
                else:
                    # Something went very wrong!
                    size_before = os.stat(abs_path).st_size
                    os.remove(abs_path)
                    print(
                        "The file {} was too small! ({} bytes)".format(
                            abs_path, size_before
                        )
                    )


class ZopfliAndBrotliPipelineCachedStorage(
    ZopfliAndBrotliMixin, PipelineManifestStorage
):
    """Same as pipeline.storage.PipelineManifestStorage but runs zopfli and brotli
    on the files.
    """
