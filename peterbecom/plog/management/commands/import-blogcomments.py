import json

from peterbecom.base.basecommand import BaseCommand
from peterbecom.plog.models import BlogComment, BlogItem


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("jsonfilepath")
        parser.add_argument("--limit", default=500)

    def _handle(self, **options):
        limit = int(options["limit"])
        with open(options["jsonfilepath"]) as f:
            imported = json.load(f)

        _cache = {}

        def get_blogitem(oid):
            try:
                found = BlogItem.objects.get(oid=oid)
            except BlogItem.DoesNotExist:
                found = None
            _cache[oid] = found
            return found

        already = notfound = notfound_parent = new = 0
        for comment in imported:
            blogitem = get_blogitem(comment["blogitem"])
            if not blogitem:
                notfound += 1
                continue

            if BlogComment.objects.filter(oid=comment["oid"]).exists():
                # print("ALREADY!", comment['oid'])
                already += 1
                continue

            parent = None
            if comment["parent"]:
                try:
                    parent = BlogComment.objects.get(oid=comment["parent"])
                except BlogComment.DoesNotExist:
                    notfound_parent += 1
                    continue

            print("NEW!", comment["oid"], already)

            BlogComment.objects.create(
                oid=comment["oid"],
                blogitem=blogitem,
                parent=parent,
                approved=comment["approved"],
                comment=comment["comment"],
                comment_rendered=comment["comment_rendered"],
                add_date=comment["add_date"],
                modify_date=comment["modify_date"],
                name=comment["name"],
                email=comment["email"],
                user_agent=comment["user_agent"],
                ip_address=comment["ip_address"],
            )

            new += 1
            if new >= limit:
                print("Limit broken!", new)
                break

        print("ALREADY:             {}".format(already))
        print("NOTFOUND (blogitem): {}".format(notfound))
        print("NOTFOUND (parent):   {}".format(notfound_parent))
        print("IMPORTED NEW:        {}".format(new))

        # qs = BlogComment.objects.all()
        # if options["oids"]:
        #     qs = qs.filter(blogitem__oid__in=options["oids"])

        # exported = []
        # exported_oids = set()

        # def export(comment):
        #     if comment.parent:
        #         export(comment.parent)

        #     if comment.oid in exported_oids:
        #         return
        #     exported_oids.add(comment.oid)
        #     item = {
        #         "oid": comment.oid,
        #         "blogitem": comment.blogitem.oid,
        #         "parent": comment.parent.oid if comment.parent else None,
        #         "approved": comment.approved,
        #         "comment": comment.comment,
        #         "comment_rendered": comment.comment_rendered,
        #         "add_date": comment.add_date.isoformat(),
        #         "modify_date": comment.modify_date.isoformat(),
        #         "name": comment.name,
        #         "email": comment.email,
        #         "user_agent": comment.user_agent,
        #         "ip_address": comment.ip_address,
        #     }
        #     exported.append(item)

        # for comment in qs.select_related("blogitem").order_by("-add_date")[:limit]:
        #     export(comment)

        # with open("exported-blogcomments.json", "w") as f:
        #     json.dump(exported, f, indent=3)
