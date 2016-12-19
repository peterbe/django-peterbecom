import datetime

from celery.task import task


@task()
def sample_task(filepath):
    print("Writing to filepath", filepath)
    with open(filepath, 'w') as f:
        written = datetime.datetime.utcnow().strftime('%b %H:%M:%S\n')
        print('\t', 'wrote', written)
        f.write(written)
