from peterbecom.base.basecommand import BaseCommand


class Command(BaseCommand):
    def handle(self, **options):
        raise NotImplementedError(
            "Use the periodic task in "
            "peterbecom.base.tasks.purge_old_postprocessings instead!!!"
        )
