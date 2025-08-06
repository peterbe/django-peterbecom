import json

from django.core.management.base import BaseCommand

from peterbecom.plog.models import BlogComment, BlogItem


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("jsonfilepath")
        parser.add_argument("--limit", default=500)
        parser.add_argument("-b", "--in-bulk", action="store_true", default=False)

    def handle(self, **options):
        limit = int(options["limit"])
        in_bulk = options["in_bulk"]
        with open(options["jsonfilepath"]) as f:
            imported = json.load(f)

        _cache = {}

        def get_blogitem(oid):
            if oid in _cache:
                return _cache[oid]
            try:
                found = BlogItem.objects.get(oid=oid)
            except BlogItem.DoesNotExist:
                found = None
            _cache[oid] = found
            return found

        bulk = []
        new_comment_oids = set()
        all_know_comment_oids = set(
            BlogComment.objects.all().values_list("oid", flat=True)
        )

        already = notfound = notfound_parent = new = 0
        for comment in imported:
            blogitem = get_blogitem(comment["blogitem"])
            if not blogitem:
                notfound += 1
                continue

            # if BlogComment.objects.filter(oid=comment["oid"]).exists():
            if comment["oid"] in all_know_comment_oids:
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
            make = BlogComment.objects.create
            if in_bulk:
                make = BlogComment
            made = make(
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
            new_comment_oids.add(comment["oid"])
            if in_bulk:
                bulk.append(made)
                if len(bulk) >= 10:
                    print("Writing bulk of", len(bulk))
                    BlogComment.objects.bulk_create(bulk)
                    bulk = []

            new += 1
            if new >= limit:
                print("Limit broken!", new)
                break

        if bulk:
            print("Writing bulk of", len(bulk))
            BlogComment.objects.bulk_create(bulk)

        print("ALREADY:             {}".format(already))
        print("NOTFOUND (blogitem): {}".format(notfound))
        print("NOTFOUND (parent):   {}".format(notfound_parent))
        print("IMPORTED NEW:        {}".format(new))
