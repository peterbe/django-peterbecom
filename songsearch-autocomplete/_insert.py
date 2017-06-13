#!/usr/bin/env python3.5

from glob import glob
import os

CDN = os.environ.get('CDN', 'https://cdn-2916.kxcdn.com')

BLOCK = """
<script>
(function() {
  var link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = '{cdn}/{csspath}';
  link.type = 'text/css';
  var head = document.head || document.getElementsByTagName("head")[0];
  head.insertBefore(link, head.lastChild);
})()
</script>
<script src="{cdn}/{jspath}" defer></script>
"""


def run():

    webroot = os.path.abspath('../peterbecom-static-content')
    csspath, = glob(os.path.join(webroot, 'songsearch-autocomplete/css/*.css'))
    jspath, = glob(os.path.join(webroot, 'songsearch-autocomplete/js/*.js'))
    csspath = csspath.replace(webroot + '/', '')
    jspath = jspath.replace(webroot + '/', '')

    block = BLOCK.replace('{cdn}', CDN).replace('{csspath}', csspath).replace('{jspath}', jspath)
    block = block.strip()
    template = '../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html'
    with open(template) as f:
        content = f.read()
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
        content = content.replace('</body>', '{}\n{}\n{}\n</body>'.format(header, block, footer))
    #print(content)
    with open(template, 'w') as f:
        f.write(content)

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(run())
