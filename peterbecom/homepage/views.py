import io
import logging
import os
import random
import re
import time
from urllib.parse import urlparse

import py_avataaars
from django import http
from django.conf import settings
from django.db.models import Max
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.views import static
from django.views.decorators.cache import cache_control, never_cache
from django_redis import get_redis_connection
from huey import crontab
from huey.contrib.djhuey import periodic_task, task
from lxml import etree

from peterbecom.base.decorators import lock_decorator
from peterbecom.base.models import AnalyticsEvent
from peterbecom.base.utils import get_base_url
from peterbecom.plog.models import BlogComment, BlogItem, BlogItemDailyHits

from .models import CatchallURL

logger = logging.getLogger("homepage")

redis_client = get_redis_connection("default")

ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4


def home(request, oc=None, page=1):
    return http.HttpResponse("deprecated. Use next\n")


@cache_control(public=True, max_age=ONE_WEEK)
def sitemap(request):
    base_url = get_base_url(request)
    root = etree.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    added = set()

    def add(loc, lastmod=None, changefreq="monthly", priority=None):
        loc = base_url + loc
        if loc in added:
            return
        added.add(loc)

        url = etree.SubElement(root, "url")
        etree.SubElement(url, "loc").text = loc
        if lastmod:
            etree.SubElement(url, "lastmod").text = lastmod.strftime("%Y-%m-%d")
        if priority:
            etree.SubElement(url, "priority").text = "{:.1f}".format(priority)
        if changefreq:
            etree.SubElement(url, "changefreq").text = changefreq

    now = timezone.now()
    blogitems = BlogItem.objects.filter(pub_date__lt=now, archived__isnull=True)
    latest_pub_date = blogitems.aggregate(pub_date=Max("pub_date"))["pub_date"]
    add("/", priority=1.0, changefreq="daily", lastmod=latest_pub_date)
    add("/about", changefreq="weekly", priority=0.5)
    add("/contact", changefreq="weekly", priority=0.5)
    add("/plog/blogitem-040601-1", changefreq="daily", priority=1.0)  # exception

    for page in range(2, settings.MAX_BLOGCOMMENT_PAGES + 1):
        add(f"/plog/blogitem-040601-1/p{page}", changefreq="daily", priority=0.9)

    # So when querying in various ways, we can skip some that are
    # already added.
    already_ids = set()

    # All blog items with a recent comment
    comments_qs = (
        BlogComment.objects.filter(approved=True, blogitem__isnull=False)
        .exclude(
            # exception since it's handled (earlier) manually
            blogitem__oid="blogitem-040601-1"
        )
        .order_by("-modify_date")
    )
    for comment in comments_qs.select_related("blogitem").values(
        "blogitem__id", "blogitem__oid", "modify_date"
    )[:100]:
        already_ids.add(comment["blogitem__id"])
        add(
            f"/plog/{comment['blogitem__oid']}",
            lastmod=comment["modify_date"],
            changefreq="daily",
        )

    # Most popular pages that haven't got recent comments
    for days_back in range(2, 5):
        popular_qs = (
            BlogItemDailyHits.objects.exclude(blogitem__id__in=already_ids)
            # This gives us the most popular, in recent days
            .filter(
                date__gt=timezone.now() - timezone.timedelta(days=days_back),
            )
            .order_by("-total_hits")
        )
        for daily_hit in popular_qs.values(
            "date",
            "total_hits",
            "blogitem__id",
            "blogitem__oid",
        )[:100]:
            already_ids.add(daily_hit["blogitem__id"])
            add(
                f"/plog/{daily_hit['blogitem__oid']}",
                changefreq="weekly",
            )

    # Now for all the rest
    blogitem_qs = (
        BlogItem.objects.exclude(id__in=already_ids)
        .filter(pub_date__lt=timezone.now())
        .order_by("-pub_date")
    )
    for item in blogitem_qs.values("id", "oid", "pub_date")[:1000]:
        already_ids.add(item["id"])
        add(
            f"/plog/{item['oid']}",
            changefreq="monthly",
            lastmod=item["pub_date"],
        )

    # (Temporary) add some recent songs
    events_qs = AnalyticsEvent.objects.filter(
        type="pageview",
        url__startswith="https://www.peterbe.com/plog/blogitem-040601-1/song/",
    ).order_by("-created")
    for event in events_qs.values("url", "created")[:100]:
        url_path = urlparse(event["url"]).path
        add(url_path, lastmod=event["created"], changefreq="weekly")

    # (Temporary) add some recent searches
    events_qs = AnalyticsEvent.objects.filter(
        type="pageview",
        url__startswith="https://www.peterbe.com/plog/blogitem-040601-1/q/",
    ).order_by("-created")
    for event in events_qs.values("url", "created")[:100]:
        url_path = urlparse(event["url"]).path
        add(url_path, lastmod=event["created"], changefreq="weekly")

    xml_output = b'<?xml version="1.0" encoding="utf-8"?>\n'
    xml_output += etree.tostring(root, pretty_print=True)
    return http.HttpResponse(xml_output, content_type="text/xml")


def catchall(request, path):
    if path.startswith("static/"):
        # This only really happens when there's no Nginx at play.
        # For example, when the mincss post process thing runs, it's
        # forced to download the 'localhost:8000/static/main.©e9fc100fa.css'
        # file.
        return static.serve(
            request, path.replace("static/", ""), document_root=settings.STATIC_ROOT
        )
    if path.startswith("cache/"):
        # This only really happens when there's no Nginx at play.
        # For example, when the mincss post process thing runs, it's
        # forced to download the 'localhost:8000/cache/1e/a7/1ea7b1a42e91c4.png'
        # file.
        return static.serve(
            request,
            path.replace("cache/", ""),
            document_root=settings.BASE_DIR / "cache",
        )
    if path.startswith("q/") and path.count("/") == 1:
        # E.g. www.peterbe.com/q/have%20to%20learn
        url = "https://songsear.ch/" + path
        return http.HttpResponsePermanentRedirect(url)

    if path in OLD_ALIASES:
        url = f"/plog/{OLD_ALIASES[path]}"
        return http.HttpResponsePermanentRedirect(url)

    if path.endswith("/index.html") and re.findall(r"^p\d+\/index\.html", path):
        return http.HttpResponseRedirect(f"/{path.replace('/index.html', '')}")

    lower_endings = (".asp", ".aspx", ".xml", ".php", ".jpg/view", ".rar", ".env")
    if any(path.lower().endswith(x) for x in lower_endings):
        return http.HttpResponse("Not found", status=404)
    if path == "...":
        return redirect("/")
    if path.startswith("cdn-2916.kxcdn.com/"):
        return redirect("https://" + path)

    CatchallURL.upsert(path, last_referer=request.headers.get("Referer"))
    print(f"CATCHALL NOTHING: {path!r}\tReferer={request.headers.get('Referer')!r}")

    raise http.Http404(path)


# A log time ago I used to have alias that would match at the root level
# A request for `/10-reasons-for-web-standards` was meant to mean
# the same as `/plog/blogitem-040606-1`.
# Gotto deal with that legacy.
OLD_ALIASES = {
    "10-reasons-for-web-standards": "blogitem-040606-1",
    "30-days-solid-McDonalds-diet-experiment": "blogitem-20040129-1700",
    "5-most-spectacular-photos-of-2003": "blogitem-040408-1",
    "A-jerk-with-a-good-website": "blogitem-20031223-1200",
    "About-Ricardo-Semler-and-Semco": "blogitem-040419-1",
    "Accessible-Pop-Up-script": "blogitem-040608-1",
    "Adding-a-year-in-PostgreSQL": "blogitem-040204-1",
    "Afghan-national-sport-photos": "blogitem-040619-1",
    "Ang-Lee-slow-motion-but-not": "blogitem-20030711-0957",
    "Anna-and-Johan-photo-modelling": "blogitem-040420-1",
    "Anti-email-harvesting-with-JavaScript": "blogitem-040401-1",
    "Apostrophes-in-predictive-text": "blogitem-040306-1",
    "Best-water": "blogitem-040224-1",
    "Bugknits": "blogitem-040225-1",
    "Bush-country": "blogitem-041028-2",
    "Bush-votes-inverse-proportional-to-education-and-IQ": "blogitem-040517-1",
    "CPU-info": "blogitem-040302-1",
    "Can-you-add-them-all-up": "blogitem-040530-1",
    "Challenge-Osama": "blogitem-040402-1",
    "Changing-textarea-size": "blogitem-040818-1",
    "City_Islington-kung-fu-charity-event": "kungfu-charity-event",
    "Classic-Movie-Scripts": "blogitem-040812-1",
    "Commodore-64-Heaven": "blogitem-040301-1",
    "Company-loyalty": "blogitem-040712-1",
    "Corp-Calendar-0.0.5": "blogitem-040610-3",
    "Creative-Commons-moving-images": "blogitem-040305-1",
    "Crontab-wizard": "blogitem-20040113-1600",
    "DOCTYPE-in-PageTemplates": "blogitem-040209-1",
    "Dans-just-been-to-Sweden": "blogitem-040623-1",
    "Data-Structures-and-Algorithms-in-Python": "blogitem-20031015-1820",
    "Date-formatting-in-python-or-in-PostgreSQL": "blogitem-040720-1",
    "Date-plus-years-or-months-or-weeks": "blogitem-040728-1",
    "Deep-sea-fish": "blogitem-040310-1",
    "Different-phone-same-number": "blogitem-040610-2",
    "Disable-Caps-Lock-in-Linux": "blogitem-041021-1",
    "Distributed-compiling-with-distcc": "blogitem-040509-1",
    "Do-you-know-about-Firefox": "blogitem-041101-1",
    "Email-your-friends_reminder_web_application": "blogitem-040828-1",
    "Eterm-and-Tkinter": "Eterm-and-Tkinter",
    "Evil-HTML-frames": "blogitem-040627-1",
    "Experimenting-with-binoculars": "blogitem-040531-1",
    "FWC-November-competition-video": "blogitem-040330-1",
    "Fat-food-fat-kids": "blogitem-040328-1",
    "Film-Music-by-Alfred-Schnittke": "blogitem-040814-1",
    "Find-song-by-lyrics": "blogitem-040601-1",
    "Findory-Blogory,-like-Google-News-Alerts-but-for-blogs": "blogitem-040903-1",
    "Finished-my-dissertation": "blogitem-040315-2",
    "Food-from-Sweden": "blogitem-040423-1",
    "Good-summary-about-Ricardo-Semler": "blogitem-20030914-0056",
    "Google-News-Alerts-BETA": "blogitem-20030929-1136",
    "Google-PageRank-matrix-calculator": "blogitem-040511-1",
    "Google-as-calculator": "blogitem-20030831-2251",
    "Google-hardware-history": "blogitem-040515-1",
    "Gota-Kanal-2004-holiday-photos": "blogitem-040712-2",
    "Grep-in-Jed": "blogitem-20040127-1500",
    "Heil-Jed-and-Dave-Kuhlman": "blogitem-040508-1",
    "Hit-the-penguin": "blogitem-20040123-1500",
    "Holiday-for-a-week": "blogitem-040626-1",
    "Honesty-and-advertising-on-Gizmodo": "blogitem-040718-1",
    "How-to-fold-clothes": "blogitem-040407-1",
    "How-to-not-get-any-spam": "blogitem-20030731-1150",
    "I-Am-American": "blogitem-040525-1",
    "I-hate-Carphone-Warehouse-and-Lifeline": "blogitem-040609-2",
    "Idea-A-new-anti-spam-law": "blogitem-040830-1",
    "Impressive-baby-photos-website": "blogitem-040612-1",
    "Integer-division-in-programming-languages": "blogitem-040804-1",
    "Intel.com-incompatible-to-Mozilla": "blogitem-040723-1",
    "Jaguar-cars-website": "blogitem-040524-1",
    "Kill-Bill-flash-game": "blogitem-040416-1",
    "Krispy-Kreme-doughnuts-store-opening": "blogitem-040513-1",
    "Kung-fu-East-London": "kung-fu-in-london-east",
    "Kung-fu-photos-from-Varberg-Sweden": "blogitem-040616-1",
    "LaTeX-Word-Counter": "blogitem-040412-1",
    "Labels-in-HTML-forms": "blogitem-20040123-1900",
    "Life-of-Pi": "blogitem-040709-1",
    "Lost-In-Translation": "blogitem-20040116-0200",
    "Lost-my-mobile-phone": "blogitem-040606-2",
    "Make-your-own-3-D-pictures": "blogitem-040731-1",
    "Massrenaming-with-shell-and-python": "blogitem-041028-1",
    "McDonalds-Calories": "blogitem-040528-1",
    "Metamorphosis-by-Franz-Kafka": "blogitem-040331-1",
    "Molvania": "blogitem-040503-1",
    "Moscow-Metro": "blogitem-20031201-1500",
    "Most-common-English-words": "blogitem-040729-1",
    "My-Secret-Life-As-A-Prostitute": "blogitem-040604-1",
    "My-dissertation-report": "blogitem-040408-2",
    "Neon-Brite": "blogitem-040223-1",
    "Nice-date-input": "blogitem-20031017-1526",
    "Nicking-images-from-our-website": "blogitem-040607-1",
    "No-more-university-for-me": "blogitem-040523-1",
    "Now-I-have-a-Gmail-account": "blogitem-040629-1",
    "Obfuscating-C-contest": "blogitem-040507-1",
    "Obsolete-Computer-Museum": "blogitem-040810-1",
    "On-the-amount-of-spam": "blogitem-040714-1",
    "On-training-camp-for-a-week": "blogitem-20030823-0646",
    "One-hot-ear": "blogitem-20031027-2106",
    "Optimized-stylesheets": "blogitem-040304-2",
    "Outbreak-fight-the-viruses": "blogitem-040505-1",
    "Overcomplicated-password-requirements-on-Oystercard.com": "blogitem-040802-1",
    "PSP-Python-Server-Pages": "blogitem-040309-1",
    "PageRank-in-Python": "blogitem-040321-1",
    "Paper-Wars": "blogitem-040716-1",
    "Pass-This-On": "blogitem-040303-1",
    "PayPalSucks.com": "blogitem-20040204-1400",
    "Pencil-Art": "mesmerizing-pencil-art",
    "People-who-really-cant-think-in-numbers": "blogitem-040820-1",
    "Photos-from-Mars": "blogitem-20040107-1300",
    "PixelField-a-game-for-pixel-lovers": "blogitem-040824-1",
    "PlogRank-my-own-PageRank-application": "blogitem-040521-1",
    "PostgreSQL-MySQL-or-SQLite": "blogitem-040404-1",
    "Practical-CSS": "blogitem-040224-2",
    "Pretty-print-SQL-script": "blogitem-040806-1",
    "Psychiatric-med-student-Michelles-story": "blogitem-040808-1",
    "Pylets": "blogitem-040326-1",
    "Python-inspect-module": "blogitem-040816-1",
    "Python-unzipped": "blogitem-040311-1",
    "Really-hate-C.html": "blogitem-040317-3",
    "Reindexing-AVI-films-with-mplayer": "blogitem-041026-1",
    "Same-but-new-keyboard": "blogitem-20040121-0100",
    "Settings-in-.Xdefaults": "blogitem-041103-1",
    "Share-Your-OPML": "blogitem-040227-2",
    "Shark-kayak": "shark-kayak",
    "Smooth-anchor-scrolling-Javascript": "smooth-anchor-scrolling",
    "Snow-Sculpture-Championships": "blogitem-20031215-1500",
    "Some-new-Kung-Fu-photos": "blogitem-20030820-1426",
    "SquareOneTV": "blogitem-040609-1",
    "Squid-in-front-of-my-Zope": "blogitem-20030730-1119",
    "StreetArt-in-London": "blogitem-040229-1",
    "TBODY-tag-in-a-XHTML-table": "blogitem-040625-1",
    "Tell-me-your-birthday": "blogitem-040901-1",
    "Test-your-computer-secretary-skills": "blogitem-040610-1",
    "The-Dead-Zone.html": "blogitem-040315-1",
    "The-Linux-Cookbook": "blogitem-20031208-0100",
    "The-Seven-day-Weekend": "blogitem-20030814-0138",
    "The-Worlds-Top-100-Wonders": "blogitem-040707-1",
    "The-importance-of-being-findable": "blogitem-040414-1",
    "The-meaning-of-hacking": "blogitem-040313-1",
    "Throw-the-penguin": "blogitem-040421-1",
    "Time-Machine-Ballistics": "blogitem-041024-1",
    "To-readline-or-readlines": "blogitem-040312-1",
    "Two-done-three-to-go": "blogitem-040514-1",
    "US-Zip-codes": "blogitem-20040107-0100",
    "Ugly-footballers": "blogitem-040826-1",
    "Underwater-MP3-player": "blogitem-040621-1",
    "University-results": "blogitem-040722-1",
    "Unusual-job-offer": "blogitem-040303-2",
    "Urwid": "blogitem-041030-1",
    "Virtual-feminization": "blogitem-040316-1",
    "Vivisimo-clustered-searching": "blogitem-20040108-1600",
    "Volvo-advert": "blogitem-040317-1",
    "WEBoggle": "blogitem-040220-1",
    "WYSIWYG-inline-HTML-editors": "blogitem-040725-1",
    "Washing-sense-of-humour": "blogitem-040608-2",
    "Why-should-I-use-XHTML": "blogitem-040516-1",
    "World-Oil-Depletion-and-the-Inevitable-Crisis": "blogitem-040727-1",
    "World-Press-Photo": "blogitem-040304-1",
    "Worst-Album-Covers-Ever": "blogitem-20031107-0300",
    "XHTML,HTML,CSS-compressor": "blogitem-040406-1",
    "Zurich-tram-service-problem": "blogitem-040511-2",
    "anti-email-harvesting": "blogitem-040226-1",
    "shit-about-shit": "blogitem-040228-1",
    "stradbally": "blogitem-040617-1",
    "uninstall-LeakFinder": "blogitem-040308-1",
    "website-about-Shallots": "blogitem-040425-1",
}


def huey_test(request):
    a = int(request.GET.get("a", 1))
    b = int(request.GET.get("b", 2))
    crash = request.GET.get("crash")
    wait = request.GET.get("wait")
    sleep = float(request.GET.get("sleep", 0.2))
    task_function = sample_huey_task
    if request.GET.get("orm"):
        task_function = sample_huey_task_with_orm
    if settings.HUEY.get("store_results"):
        queued = task_function(a, b, crash=crash, sleep=sleep)
        result = queued()
        # print("Result:", repr(result))
        for i in range(10):
            time.sleep(0.1 * (i + 1))
            result = queued()
            # print(i, "\tResult:", repr(result))
            if result is not None:
                return http.HttpResponse(str(result))
    elif wait:
        fp = "/tmp/huey.result.{}".format(time.time())
        try:
            task_function(a, b, crash=crash, output_filepath=fp, sleep=sleep)
            slept = 0
            for i in range(10):
                sleep = 0.1 * (i + 1)
                # print("SLEEP", sleep)
                time.sleep(sleep)
                slept += sleep
                try:
                    with open(fp) as f:
                        result = f.read()
                except FileNotFoundError:
                    continue
                return http.HttpResponse("{} after {}s".format(result, slept))
        finally:
            if os.path.isfile(fp):
                os.remove(fp)
    else:
        task_function(a, b, crash=crash, sleep=sleep)

    return http.HttpResponse("OK")


class HueySampleError(Exception):
    """Only for testing."""


@task()
def sample_huey_task(a, b, crash=None, output_filepath=None, sleep=0):
    if sleep:
        time.sleep(sleep)
    if crash:
        raise HueySampleError(crash)
    result = a * b
    if output_filepath:
        with open(output_filepath, "w") as f:
            f.write("{}".format(result))
    else:
        return result


@task()
def sample_huey_task_with_orm(a, b, crash=None, output_filepath=None, sleep=0):
    if sleep:
        time.sleep(sleep)
    if crash:
        raise HueySampleError(crash)
    result = BlogComment.objects.all().count()
    if output_filepath:
        with open(output_filepath, "w") as f:
            f.write("{}".format(result))
    else:
        return result


def dynamic_page(request):
    return http.HttpResponse("Current time is: {}\n".format(timezone.now()))


# NOTE: This is no longer linked to. Can delete in 2023.
@cache_control(public=True, max_age=ONE_WEEK)
def avatar_image_test_page(request):
    return redirect("/plog/random-avatars-in-django-python")


short_term_random_avatar = None


def avatar_image(request, seed=None):
    # If there's any query string in the URL that isn't recognized, 301 redirect
    # it away so it can't be cache bypassed.
    querystring_keys = [x for x in request.GET.keys() if x != "seed"]
    if querystring_keys:
        return redirect(reverse("homepage:avatar_image_seed", args=("random",)))

    if not seed:
        seed = request.GET.get("seed") or "random"

    if seed != "random":
        random.seed(seed)

    # Try to read from the "global cache first"
    global short_term_random_avatar
    if short_term_random_avatar and isinstance(short_term_random_avatar, tuple):
        short_term_random_avatar = {}

    if (
        short_term_random_avatar
        and time.time() - short_term_random_avatar["time"] < 3
        and short_term_random_avatar["seed"] == seed
    ):
        print("Got RANDOM AVATAR from short-term", request.META.get("HTTP_REFERER"))
        random_avatar = short_term_random_avatar["avatar"]
    else:
        random_avatar = redis_client.rpop(REDIS_RANDOM_AVATARS_LIST_KEY)
        print(
            f"RANDOM AVATAR: {random_avatar and 'Redis HIT' or 'Redis Miss'}",
            request.META.get("HTTP_REFERER"),
        )
        if not random_avatar:
            random_avatar = get_random_avatar()
            print("Generated new RANDOM AVATAR", request.META.get("HTTP_REFERER"))
            fill_random_avatars_redis_list()

        short_term_random_avatar = {
            "time": time.time(),
            "avatar": random_avatar,
            "seed": seed,
        }

    response = http.HttpResponse(random_avatar)
    response["content-type"] = "image/png"
    if seed == "random":
        # Aug 8, had to do this to lift load off the server.
        patch_cache_control(response, max_age=60 * 2, public=True)
        # add_never_cache_headers(response)
    else:
        patch_cache_control(response, max_age=60 * 2, public=True)

    return response


REDIS_RANDOM_AVATARS_LIST_KEY = "random_avatars_list"


@periodic_task(crontab(minute="*/2"))
def keep_random_avatars_redis_list_filled():
    fill_random_avatars_redis_list_filled()


@lock_decorator()
def fill_random_avatars_redis_list():
    fill_random_avatars_redis_list_filled()


def fill_random_avatars_redis_list_filled():
    key = REDIS_RANDOM_AVATARS_LIST_KEY

    count = redis_client.llen(key)
    print(f"# random avatars in Redis: {count} ({timezone.now()})")
    if count >= settings.NUMBER_AVATARS_PREMADE:
        return

    # Because of how Huey works, make sure you import this here
    # within the function. Weird but necessary.
    import xml.etree.ElementTree as ET

    while redis_client.llen(key) < settings.NUMBER_AVATARS_PREMADE:
        random_avatars = []
        for _ in range(int(settings.NUMBER_AVATARS_PREMADE / 10)):
            try:
                random_avatars.append(get_random_avatar())
            except ET.ParseError:
                # Happens because of https://github.com/kebu/py-avataaars/issues/7
                continue

        redis_client.lpush(key, *random_avatars)
        print(
            f"# random avatars in Redis (after): "
            f"{redis_client.llen(key)} ({timezone.now()})"
        )


def get_random_avatar():
    bytes = io.BytesIO()

    def r(enum_):
        return random.choice(list(enum_))

    avatar = py_avataaars.PyAvataaar(
        style=py_avataaars.AvatarStyle.CIRCLE,
        skin_color=r(py_avataaars.SkinColor),
        hair_color=r(py_avataaars.HairColor),
        facial_hair_type=r(py_avataaars.FacialHairType),
        facial_hair_color=r(py_avataaars.HairColor),
        top_type=r(py_avataaars.TopType),
        hat_color=r(py_avataaars.Color),
        mouth_type=r(py_avataaars.MouthType),
        eye_type=r(py_avataaars.EyesType),
        eyebrow_type=r(py_avataaars.EyebrowType),
        nose_type=r(py_avataaars.NoseType),
        accessories_type=r(py_avataaars.AccessoriesType),
        clothe_type=r(py_avataaars.ClotheType),
        clothe_color=r(py_avataaars.Color),
        clothe_graphic_type=r(py_avataaars.ClotheGraphicType),
    )
    avatar.render_png_file(bytes)

    return bytes.getvalue()


@never_cache
def preview_500(request):
    print("HI there4")
    return render(request, "500.html")


ROBOTS_TXT = """
User-agent: *
"""


@cache_control(public=True, max_age=ONE_WEEK)
def robots_txt(request):
    return http.HttpResponse(f"{ROBOTS_TXT.strip()}\n", content_type="text/plain")
