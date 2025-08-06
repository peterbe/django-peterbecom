import json

from django.core.management.base import BaseCommand

from peterbecom.plog.models import BlogComment


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("oids", nargs="?")
        parser.add_argument("--limit", default=500)
        parser.add_argument("--offset", default=0)

    def handle(self, **options):
        limit = int(options["limit"])
        offset = int(options["offset"])
        qs = BlogComment.objects.all()
        if options["oids"]:
            qs = qs.filter(blogitem__oid__in=options["oids"])

        exported = []
        exported_oids = set()

        def export(comment):
            if comment.parent:
                export(comment.parent)

            if comment.oid in exported_oids:
                return
            exported_oids.add(comment.oid)
            item = {
                "oid": comment.oid,
                "blogitem": comment.blogitem.oid,
                "parent": comment.parent.oid if comment.parent else None,
                "approved": comment.approved,
                "comment": comment.comment,
                "comment_rendered": comment.comment_rendered,
                "add_date": comment.add_date.isoformat(),
                "modify_date": comment.modify_date.isoformat(),
                "name": comment.name,
                "email": comment.email,
                "user_agent": comment.user_agent,
                "ip_address": comment.ip_address,
            }
            exported.append(item)

        m, n = offset, limit + offset

        for comment in qs.select_related("blogitem").order_by("-add_date")[m:n]:
            export(comment)

        with open("exported-blogcomments.json", "w") as f:
            json.dump(exported, f, indent=3)
