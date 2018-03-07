import subprocess

from pipeline.compressors import CompressorBase
from django.conf import settings


class CSSOCompressor(CompressorBase):

    def compress_css(self, css):
        proc = subprocess.Popen(
            [settings.PIPELINE['CSSO_BINARY'], '--restructure-off'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        css_out = proc.communicate(
            input=css.encode('utf-8')
        )[0].decode('utf-8')
        # was_size = len(css)
        # new_size = len(css_out)
        # print('FROM {} to {} Saved {}  ({!r})'.format(
        #     was_size,
        #     new_size,
        #     was_size - new_size,
        #     css_out[:50]
        # ))
        return css_out
