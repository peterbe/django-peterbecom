from io import BytesIO

from django.conf import settings
from django.contrib.staticfiles.utils import matches_patterns
from django.core.files.base import File
from pipeline.storage import PipelineCachedStorage
from zopfli import gzip as zopfli


class ZopfliMixin(object):
    name_patterns = ("*.css", "*.js", "*.svg")

    # 'numiterations' default is 15 in
    # https://github.com/obp/py-zopfli/blob/master/src/zopflimodule.c
    numiterations = getattr(settings, "ZOPFLI_COMPRESS_NUM_ITERATIONS", 100)
    minimum_size_bytes = getattr(settings, "ZOPFLI_COMPRESS_MIN_SIZE_BYTES", 256)
    only_hashed_files = getattr(settings, "ZOPFLI_COMPRESS_ONLY_HASHED_FILES", True)

    def _compress(self, original_file):
        content = BytesIO(
            zopfli.compress(original_file.read(), numiterations=self.numiterations)
        )
        content.seek(0)
        return File(content)

    def post_process(self, paths, dry_run=False, **options):
        super_class = super(ZopfliMixin, self)
        processed_hash_names = []
        if hasattr(super_class, "post_process"):
            for name, hashed_name, processed in super_class.post_process(
                paths.copy(), dry_run, **options
            ):
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
            if self.exists(gzipped_path):
                # This is the beauty of using django_pipeline.
                # If the .gz file exists, it means the source of it hasn't changed
                # even though it was re-written to disk, because we only bother
                # with files with hashed in the name.
                continue
            gzipped_file = self._compress(original_file)
            gzipped_path = self.save(gzipped_path, gzipped_file)
            yield gzipped_path, gzipped_path, True


class ZopfliPipelineCachedStorage(ZopfliMixin, PipelineCachedStorage):
    """Same as pipeline.storage.PipelineCachedStorage but runs zopfli on the files
    """
