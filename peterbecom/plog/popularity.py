import math

from django.db import transaction

from peterbecom.plog.models import BlogItem


def score_to_popularity(score):
    return math.log10(1 + score)


def update_all(verbose=False, limit=1000, dry_run=False, reindex=False):
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
            LIMIT {limit}
        """.format(limit=limit)
    )

    ids = []
    with transaction.atomic():
        for record in query:
            popularity = score_to_popularity(record.score)
            difference = abs(popularity - (record.popularity or 0.0))
            if difference < 0.00001:
                # don't bother if it hasn't changed much since the last run.
                continue
            ids.append(record.id)
            if not dry_run:
                BlogItem.objects.filter(id=record.id).update(popularity=popularity)

    if not dry_run and ids:
        BlogItem.index_all_blogitems(ids_only=ids, verbose=verbose)

    return ids
