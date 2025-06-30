from pathlib import Path

from django.conf import settings

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--filename", default=settings.SYNONYM_FILE_NAME)

    def handle(self, **options):
        synonyms_root = settings.BASE_DIR / "peterbecom/es-synonyms"
        american_british_syns_fn = synonyms_root / "be-ae.synonyms"

        all_synonyms = [
            "go => golang",
            "react => reactjs",
            "angular => angularjs",
            "mongo => mongodb",
            "postgres => postgresql",
            "dont => don't",
            "nodejs => node",
        ]

        # The file 'be-ae.synonyms' is a synonym file mapping British to American
        # English. For example 'centre => center'.
        # And also 'lustre, lustreless => luster, lusterless'
        # Because some documents use British English and some use American English
        # AND that people who search sometimes use British and sometimes use American,
        # therefore we want to match all and anything.
        # E.g. "center" should find "...the center of..." and "...the centre for..."
        # But also, should find the same when searching for "centre".
        # So, rearrange the ba-ae.synonyms file for what's called
        # "Simple expansion".
        # https://www.elastic.co/guide/en/elasticsearch/guide/current/synonyms-expand-or-contract.html#synonyms-expansion  # noqa
        #
        with open(american_british_syns_fn) as f:
            for line in f:
                if "=>" not in line or line.strip().startswith("#"):
                    continue
                all_synonyms.append(line.strip())

        filename_path = Path(options["filename"])
        with open(filename_path, "w") as f:
            for synonym in all_synonyms:
                f.write(f"{synonym}\n")

        print(f"Wrote {len(all_synonyms):,} synonyms to: {filename_path.resolve()}")

        print(
            "\nYou might want to copy this to some directory like "
            "/Users/peterbe/dev/PETERBECOM/elasticsearch-7.7.0/ or "
            "/etc/elasticsearch/"
        )
