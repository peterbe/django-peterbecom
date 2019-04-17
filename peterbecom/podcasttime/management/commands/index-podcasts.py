import time

from django.db.models import Count, Sum
from django.conf import settings

from elasticsearch_dsl.connections import connections
from elasticsearch.helpers import streaming_bulk

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast, Episode
from peterbecom.podcasttime.search import PodcastDoc


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=0, help="Number of podcasts to index")
        parser.add_argument(
            "--random",
            action="store_true",
            default=False,
            help="Randomly pick podcasts (to limit the whole process time)",
        )
        parser.add_argument(
            "--create-index",
            action="store_true",
            default=False,
            help="create index even with limit",
        )

    def _handle(self, *args, **kwargs):
        limit = int(kwargs["limit"])
        if kwargs["random"] and not limit:
            raise Exception("random but not limited")
        # if kwargs['force_create_index'] and not limit:
        #     raise Exception('force-create-index but not limited')

        iterator = Podcast.objects.filter(error__isnull=True).exclude(
            name="", last_fetch__isnull=True
        )
        if limit:
            if kwargs["random"]:
                iterator = iterator.order_by("?")[:limit]
                iterator = list(iterator)
            else:
                iterator = iterator.order_by("-modified")[:limit]

        if kwargs["create_index"]:  # or not limit:
            podcast_index = PodcastDoc._index
            podcast_index.delete(ignore=404)
            podcast_index.create()

        # Compute a big map of every podcast's total episode count
        episode_counts = {}
        all_episodes = Episode.objects.all()
        if limit:
            all_episodes = all_episodes.filter(podcast_id__in=[x.id for x in iterator])
        all_episodes_annotated = all_episodes.values("podcast_id").annotate(
            count=Count("podcast_id")
        )
        for e in all_episodes_annotated:
            episode_counts[e["podcast_id"]] = e["count"]

        duration_sums = {}
        all_durations_annotated = all_episodes.values("podcast_id").annotate(
            duration=Sum("duration")
        )
        for e in all_durations_annotated:
            duration_sums[e["podcast_id"]] = e["duration"]

        es = connections.get_connection()
        report_every = 100
        count = 0
        doc_type = Podcast._meta.verbose_name.lower()
        t0 = time.time()
        for success, doc in streaming_bulk(
            es,
            (
                m.to_search(
                    duration_sums=duration_sums, episodes_count=episode_counts
                ).to_dict(True)
                for m in iterator
            ),
            index=settings.ES_PODCAST_INDEX,
            doc_type=doc_type,
        ):
            if not success:
                print("NOT SUCCESS!", doc)
            count += 1
            if not count % report_every:
                print(count)
        t1 = time.time()

        self.out("DONE Indexing {} podcasts in {} seconds".format(count, t1 - t0))
