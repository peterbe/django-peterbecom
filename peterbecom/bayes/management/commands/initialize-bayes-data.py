import zlib
from io import BytesIO

from django.core.management.base import BaseCommand

from peterbecom.bayes.guesser import Bayes, CustomTokenizer
from peterbecom.bayes.models import BayesData


class Command(BaseCommand):
    help = "Sets up an initial BayesData topic"

    def add_arguments(self, parser):
        parser.add_argument("topic")
        parser.add_argument(
            "--case-sensitive",
            action="store_true",
            default=False,
            help="If true, don't lowercase all text. Default False",
        )

    def handle(self, **options):
        topic = options["topic"]
        guesser = Bayes(tokenizer=CustomTokenizer(lower=options["case_sensitive"]))
        bayes_data = BayesData()
        bayes_data.topic = topic
        bayes_data.options = {"case_sensitive": options["case_sensitive"]}
        with BytesIO() as f:
            guesser.save_handler(f)
            bayes_data.pickle_data = zlib.compress(f.getvalue())
            bayes_data.save()
            self.stdout.write(self.style.SUCCESS("{!r} created".format(bayes_data)))
