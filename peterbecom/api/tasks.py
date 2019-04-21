from django.template import loader
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.urls import reverse
from django.conf import settings
from huey.contrib.djhuey import task

from peterbecom.plog.models import BlogComment


@task()
def send_comment_reply_email(blogcomment_id):
    blogcomment = BlogComment.objects.get(id=blogcomment_id)
    if not blogcomment.approved:
        print("Blog comment {!r} is no longer approved".format(blogcomment))
        return

    parent = blogcomment.parent
    tos = [parent.email]
    blogitem = blogcomment.blogitem
    if blogitem.oid == "blogitem-040601-1":
        from_ = "Find song by lyrics <mail@peterbe.com>"
        subject = "Find song by lyrics: Reply to your comment"
    else:
        from_ = "Peterbe.com <mail@peterbe.com>"
        subject = "Peterbe.com: Reply to your comment"
    body = _get_comment_reply_body(blogitem, blogcomment, parent)
    send_mail(subject, body, from_, tos)


def _get_comment_reply_body(blogitem, blogcomment, parent):
    page = get_comment_page(blogcomment)
    if page > 1:
        comment_url = reverse("blog_post", args=[blogitem.oid, page])
    else:
        comment_url = reverse("blog_post", args=[blogitem.oid])

    domain = Site.objects.get_current().domain
    if domain == "peterbecom.local":
        # Useful for local dev
        base_url = "http://" + domain
    else:
        base_url = "https://" + domain
    template = loader.get_template("plog/comment_reply_body.txt")
    context = {
        "post": blogitem,
        "comment": blogcomment,
        "parent": parent,
        "base_url": base_url,
        "comment_url": comment_url,
    }
    return template.render(context).strip()


def get_comment_page(blogcomment):
    root_comment = blogcomment
    while root_comment.parent_id:
        root_comment = root_comment.parent

    qs = BlogComment.objects.filter(blogitem=blogcomment.blogitem, parent__isnull=True)
    ids = list(qs.order_by("-add_date").values_list("id", flat=True))
    per_page = settings.MAX_RECENT_COMMENTS
    for i in range(settings.MAX_BLOGCOMMENT_PAGES):
        sub_list = ids[i * per_page : (i + 1) * per_page]
        if root_comment.id in sub_list:
            return i + 1
    return 1
