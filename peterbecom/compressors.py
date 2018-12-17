import subprocess

from pipeline.compressors import CompressorBase
from django.conf import settings


class CSSOCompressor(CompressorBase):
    def compress_css(self, css):
        proc = subprocess.Popen(
            [settings.PIPELINE["CSSO_BINARY"], "--no-restructure"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        css_out = proc.communicate(input=css.encode("utf-8"))[0].decode("utf-8")
        return css_out
