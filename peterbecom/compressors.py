
import os
import tempfile

import delegator

from pipeline.compressors import CompressorBase
from django.conf import settings


class CSSOCompressor(CompressorBase):

    def compress_css(self, css):
        # Feb 2018.
        # The reason I chose to use a temporary directory and calling
        # csso with a input file and an output file is because
        # I was getting out-of-memory problems in docker.
        with tempfile.TemporaryDirectory() as dir_:
            input_fn = os.path.join(dir_, 'input.css')
            with open(input_fn, 'w') as f:
                f.write(css)
            output_fn = os.path.join(dir_, 'output.css')
            command = '{} {} {} --restructure-off'.format(
                settings.PIPELINE['CSSO_BINARY'],
                input_fn,
                output_fn
            )
            r = delegator.run(command)
            if r.return_code:
                print(command)
                raise Exception(r.return_code)
            with open(output_fn) as f:
                css_out = f.read()

        # was_size = len(css)
        # new_size = len(css_out)
        # print('FROM {} to {} Saved {}  ({!r})'.format(
        #     was_size,
        #     new_size,
        #     was_size - new_size,
        #     css_out[:50]
        # ))
        return css_out
