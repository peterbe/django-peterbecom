import hashlib
import time

from django import http
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from peterbecom.base.utils import fake_ip_address
from peterbecom.plog.models import BlogComment
from peterbecom.plog.spamprevention import (
    contains_spam_patterns,
    contains_spam_url_patterns,
    is_trash_commenter,
)
from peterbecom.plog.tasks import delete_e2e_test_comment, send_new_comment_email
from peterbecom.plog.utils import render_comment_text
from peterbecom.publicapi.forms import SubmitForm


@never_cache
@ensure_csrf_cookie
def prepare_comment(request):
    token = request.META["CSRF_COOKIE"]
    return http.JsonResponse({"csrfmiddlewaretoken": token})


@require_POST
def preview_comment(request):
    comment = (request.POST.get("comment") or "").strip()
    if not comment:
        return http.HttpResponseBadRequest("empty comment")
    if len(comment) > 10_000:
        return http.HttpResponseBadRequest("too big")

    rendered = render_comment_text(comment)
    return http.JsonResponse({"comment": rendered})


@require_POST
def submit_comment(request):
    form = SubmitForm(request.POST)
    if not form.is_valid():
        return http.JsonResponse({"error": form.errors}, status=400)

    def make_cache_key(hash):
        return f"blog_comment_hash:{hash}"

    blogitem = form.cleaned_data["oid"]
    name = form.cleaned_data["name"]
    email = form.cleaned_data["email"]
    comment = form.cleaned_data["comment"]
    parent = form.cleaned_data["parent"]
    blog_comment_hash = form.cleaned_data["hash"]

    if contains_spam_url_patterns(comment) or contains_spam_patterns(comment):
        return http.HttpResponseBadRequest("Looks too spammy")

    ip_addresses = (
        request.headers.get("x-forwarded-for") or request.META.get("REMOTE_ADDR") or ""
    )
    # X-Forwarded-For might be a comma separated list of IP addresses
    # coming from the CDN. The first is the client.
    # https://www.keycdn.com/blog/x-forwarded-for-cdn
    ip_address = [x.strip() for x in ip_addresses.split(",") if x.strip()][0]

    if ip_address == "127.0.0.1" and settings.FAKE_BLOG_COMMENT_IP_ADDRESS:
        ip_address = fake_ip_address(f"{name}{email}")

    user_agent = request.headers.get("User-Agent")

    if is_trash_commenter(name=name, email=email):
        return http.JsonResponse({"trash": True}, status=400)

    search = {"comment": comment}
    if name:
        search["name"] = name
    if email:
        search["email"] = email
    if parent:
        search["parent"] = parent

    if blog_comment_hash:
        cache_key = make_cache_key(blog_comment_hash)
        blogitem_oid = cache.get(cache_key)
        if not blogitem_oid:
            return http.HttpResponseForbidden("Edit comment hash has expired")
        try:
            blog_comment = BlogComment.objects.get(oid=blogitem_oid)
        except BlogComment.DoesNotExist:
            return http.HttpResponse("No blog comment by that OID", status=410)

        blog_comment.comment = comment
        blog_comment.name = name
        blog_comment.email = email
        blog_comment.save()
    else:
        for blog_comment in BlogComment.objects.filter(**search):
            break
        else:
            blog_comment = BlogComment.objects.create(
                oid=BlogComment.next_oid(),
                blogitem=blogitem,
                parent=parent,
                approved=False,
                comment=comment,
                name=name,
                email=email,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            try:
                blog_comment.create_geo_lookup()
            except Exception as exception:
                if settings.DEBUG:
                    raise
                print(f"WARNING! {exception!r} create_geo_lookup failed")

            if blogitem.oid != "blogitem-040601-1":
                transaction.on_commit(lambda: send_new_comment_email(blog_comment.id))

            if (
                blog_comment.name == "Playwright"
                and blog_comment.email == "playwright@peterbe.com"
            ):
                delete_e2e_test_comment(blog_comment.id, 2)

    if not blog_comment_hash:
        # Generate a non-cryptographic hash that the user can user to edit their
        # comment after they posted it.
        blog_comment_hash = hashlib.md5(
            f"{blog_comment.oid}{time.time()}".encode("utf-8")
        ).hexdigest()
        cache_key = make_cache_key(blog_comment_hash)
        hash_expiration_seconds = 60 * 60
        cache.set(cache_key, blog_comment.oid, hash_expiration_seconds)

    context = {
        "oid": blog_comment.oid,
        "hash": blog_comment_hash,
        "comment_original": blog_comment.comment,
        "comment": blog_comment.comment_rendered,
    }
    return http.JsonResponse(context)
