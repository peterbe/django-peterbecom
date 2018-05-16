#!/usr/bin/env python3.5

from glob import glob
import os
import re

CDN = os.environ.get('CDN', 'https://cdn-2916.kxcdn.com')

BLOCK = """
<style type="text/css">{csspayload}</style>
<script src="{cdn}/{jspath}" defer></script>
"""


def run():

    webroot = os.path.abspath('../peterbecom-static-content')
    csspath, = glob(os.path.join(webroot, 'songsearch-autocomplete/css/*.css'))
    jspath, = glob(os.path.join(webroot, 'songsearch-autocomplete/js/*.js'))
    jspath = jspath.replace(webroot + '/', '')

    with open(csspath) as f:
        csspayload = f.read()
        csspayload = re.sub(r'\/\*# sourceMappingURL=.*?\*\/', '', csspayload)
        csspayload = csspayload.strip()

    block = BLOCK.replace('{cdn}', CDN).replace('{csspayload}', csspayload).replace('{jspath}', jspath)
    block = block.strip()
    template = '../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html'
    with open(template) as f:
        original_content = content = f.read()
    header = '<!-- https://github.com/peterbe/django-peterbecom/tree/master/songsearch-autocomplete -->'
    start = content.find(header)
    footer = '<!-- /songsearch-autocomplete -->'
    end = content.find(footer)
    if start > -1:
        # replacement
        print('Replaced existing block', template)
        content = content[:start] + header + '\n' + block + '\n' + content[end:]
    else:
        print('Inserted new block', template)
        content = content.replace(
            '</body>', '{}\n{}\n{}\n</body>'.format(header, block, footer)
        )
    if original_content != content:
        with open(template, 'w') as f:
            f.write(content)
        print('Updated {} with new content.'.format(template))
    else:
        print('Nothing changed in the content. No write.')

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(run())
