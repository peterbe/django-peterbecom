import textwrap

from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.urls import reverse
from huey.contrib.djhuey import task

from peterbecom.plog.models import BlogComment
from peterbecom.plog.utils import get_comment_page


@task()
def send_comment_reply_email(blogcomment_id):
    blogcomment = BlogComment.objects.get(id=blogcomment_id)
    if not blogcomment.approved:
        print(f"Blog comment {blogcomment!r} is no longer approved")
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
    return f"""
This is an automatic email notification from Peterbe.com
On this page,
{base_url}{comment_url}
you wrote:

{line_indent(parent.comment)}

Now, {blogcomment.name if blogcomment.name else 'someone'} has replied with the following comment:

{line_indent(blogcomment.comment)}

To visit the page again or to respond, go to:
{base_url}{comment_url}#{parent.oid}

    """.strip()


def line_indent(text, indent=" " * 4):
    return "\n".join(
        textwrap.wrap(text, initial_indent=indent, subsequent_indent=indent)
    )
