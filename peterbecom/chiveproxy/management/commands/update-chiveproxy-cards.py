from peterbecom.base.basecommand import BaseCommand
from peterbecom.chiveproxy.views import update_cards


class Command(BaseCommand):
    def handle(self, **options):
        update_cards()
