import time

from django.core.management.base import BaseCommand
from django.db import connection
from sentence_transformers import SentenceTransformer

from peterbecom.plog.models import SearchDoc


class Command(BaseCommand):
    help = "Generate embeddings for titles and texts"

    def handle(self, *args, **options):
        print("Loading embedding model...")
        model = SentenceTransformer("all-mpnet-base-v2")

        print(SearchDoc.objects.filter(title_embedding__isnull=True).count())

        titles = {}
        texts = {}
        for id, title, text in SearchDoc.objects.values_list("id", "title", "text"):
            titles[id] = title
            texts[id] = text

        all_titles = list(titles.items())
        all_texts = list(texts.items())
        T0 = time.time()
        with connection.cursor() as cursor:
            t0 = time.time()
            for i in range(0, len(titles), 100):
                batch = all_titles[i : i + 100]
                titles = [title for _, title in batch]
                embeddings = model.encode(titles)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Generated embeddings for batch number {i // 100 + 1} ({len(batch)} items)"
                    )
                )
                for i, (id, _) in enumerate(batch):
                    cursor.execute(
                        """
                        UPDATE plog_searchdoc
                        SET title_embedding = %s
                        WHERE id = %s
                    """,
                        (embeddings[i].tolist(), id),
                    )
            t1 = time.time()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Took {t1 - t0:.2f} seconds to generate embeddings for {len(titles)} titles."
                )
            )

            t0 = time.time()
            for i in range(0, len(texts), 100):
                batch = all_texts[i : i + 100]
                texts = [text for _, text in batch]
                embeddings = model.encode(texts)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Generated embeddings for batch number {i // 100 + 1} ({len(batch)} items)"
                    )
                )
                for i, (id, _) in enumerate(batch):
                    cursor.execute(
                        """
                        UPDATE plog_searchdoc
                        SET text_embedding = %s
                        WHERE id = %s
                    """,
                        (embeddings[i].tolist(), id),
                    )
            t1 = time.time()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Took {t1 - t0:.2f} seconds to generate embeddings for {len(texts)} texts."
                )
            )

        T1 = time.time()
        self.stdout.write(
            self.style.SUCCESS(
                f"Generated embeddings for {len(texts)} texts. Took {T1 - T0:.2f} seconds."
            )
        )
