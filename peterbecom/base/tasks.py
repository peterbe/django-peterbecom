import os
import shutil

from celery import shared_task

from peterbecom.mincss_response import mincss_html


@shared_task
def post_process_cached_html(filepath, url):
    if url.startswith('http://testserver'):
        # do nothing. testing.
        return
    if not os.path.exists(filepath):
        raise ValueError(
            "{!r} does not exist and can't be post-processed".format(
                filepath,
            )
        )
    with open(filepath) as f:
        html = f.read()
        optimized_html = mincss_html(html, url)
    # if os.path.isfile(filepath + '.original'):
    #     warnings.warn('{} was already optimized'.format(filepath))
    shutil.move(filepath, filepath + '.original')
    with open(filepath, 'w') as f:
        f.write(optimized_html)
    print('mincss optimized {}'.format(filepath))
