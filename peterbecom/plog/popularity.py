from django.db import transaction

from peterbecom.plog.models import BlogItem


def update_all(verbose=False, limit=1000, dry_run=False, reindex=False):
    # Note! No limit on this. Otherwise we can't fairly normalize the scores.
    query = BlogItem.objects.raw(
        """
            WITH counts AS (
                SELECT
                    blogitem_id, count(blogitem_id) AS count
                    FROM plog_blogitemhit
                    GROUP BY blogitem_id
            )
            SELECT
                b.id, b.oid, b.title, b.popularity, count AS hits, b.pub_date,
                EXTRACT(DAYS FROM (NOW() - b.pub_date))::INT AS age,
                count / EXTRACT(DAYS FROM (NOW() - b.pub_date)) AS score
            FROM counts, plog_blogitem b
            WHERE
                blogitem_id = b.id AND (NOW() - b.pub_date) > INTERVAL '1 day'
            ORDER BY score desc
        """
    )

    normalize = {}
    previous_popularity = {}
    sum_scores = 0.0
    for record in query:
        if verbose:
            print((record.score, record.hits, record.age, record.title))
        normalize[record.id] = record.score
        previous_popularity[record.id] = record.popularity or 0.0
        sum_scores += record.score

    ids = []
    flat = [(v, k) for k, v in normalize.items()]
    flat.sort(reverse=True)
    with transaction.atomic():
        for score, id in flat[:limit]:
            popularity = score / sum_scores
            difference = abs(popularity - previous_popularity[id])
            if difference < 0.000001:
                # don't bother if it hasn't changed much since the last run.
                continue
            ids.append(id)
            if not dry_run:
                BlogItem.objects.filter(id=id).update(popularity=popularity)

    if not dry_run and ids:
        BlogItem.index_all_blogitems(ids_only=ids, verbose=verbose)

    return ids
