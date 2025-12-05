import textwrap

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from huey.contrib.djhuey import task

from peterbecom.plog.models import BlogComment
from peterbecom.plog.utils import blog_post_url


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
    html_body = _get_html_comment_body(blogitem, blogcomment, parent)

    if settings.DEBUG:
        fname = f"/tmp/reply-comment-email.{blogcomment_id}.html"
        with open(fname, "w") as f:
            f.write(html_body)
        print(f"Dumped HTML to {fname}")

    send_mail(subject, body, from_, tos, html_message=html_body)


def _get_comment_reply_body(blogitem, blogcomment, parent):
    comment_url = blog_post_url(blogitem.oid)

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

Now, {blogcomment.name if blogcomment.name else "someone"} has replied with the following comment:

{line_indent(blogcomment.comment)}

To visit the page again or to respond, go to:
{base_url}{comment_url}/comment/{blogcomment.oid}

    """.strip()


def line_indent(text, indent=" " * 4):
    return "\n".join(
        textwrap.wrap(text, initial_indent=indent, subsequent_indent=indent)
    )


def _get_html_comment_body(blogitem, blogcomment, parent):
    base_url = f"https://{Site.objects.get_current().domain}"
    if "peterbecom.local" in base_url:
        base_url = "http://localhost:4000"

    post_url = blog_post_url(blogitem.oid)
    full_post_url = f"{base_url}{post_url}"

    comment_url = f"{post_url}/comment/{parent.oid}"
    full_comment_url = f"{base_url}{comment_url}"

    parent_comment_date_human = parent.add_date.strftime("%b %d, %Y")

    return render_to_string(
        "emails/reply-comment-email.djt",
        {
            "blogitem": blogitem,
            "is_lyrics_post": blogitem.oid == "blogitem-040601-1",
            "comment_url": full_comment_url,
            "post_url": full_post_url,
            "blogcomment": blogcomment,
            "parent": parent,
            "parent_comment_date_human": parent_comment_date_human,
        },
    )
