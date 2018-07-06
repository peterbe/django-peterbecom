from django.contrib.sites.models import Site
from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast


BASE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<urlset
  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
  xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  {}
</urlset>"""


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--base-url", default=None, help="E.g https://podcasttime")
        parser.add_argument(
            "--outfile", "-o", default=None, help="If not site, use stdout"
        )

    def _handle(self, **options):
        base_url = options["base_url"]
        if not base_url:
            base_url = "https://" + Site.objects.get_current().domain
        assert "://" in base_url, base_url
        assert not base_url.endswith("/"), base_url

        def absolute_url(uri):
            return base_url + uri

        urls_xmls = []
        # Some static ones
        urls_xmls.append(
            "<url>"
            "<loc>{}</loc><priority>1.0</priority>"
            "</url>".format(absolute_url("/podcasts"))
        )
        urls_xmls.append(
            "<url>" "<loc>{}</loc>" "</url>".format(absolute_url("/about"))
        )

        qs = Podcast.objects.filter(error__isnull=True)
        for podcast in qs.order_by("-times_picked", "modified")[:49000]:
            urls_xmls.append(
                "<url>"
                "<loc>{}</loc><lastmod>{}</lastmod>"
                "</url>".format(
                    absolute_url(
                        "/podcasts/{}/{}".format(
                            podcast.id, podcast.get_or_create_slug()
                        )
                    ),
                    (podcast.latest_episode or podcast.modified).strftime("%Y-%m-%d"),
                )
            )
        sitemap_xml = BASE_TEMPLATE.format("\n".join(urls_xmls))
        if options.get("outfile"):
            with open(options["outfile"], "w") as f:
                f.write(sitemap_xml)
        else:
            print(sitemap_xml)
