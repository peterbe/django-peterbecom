from django.template import loader
from django.core.mail import send_mail
from django.contrib.sites.models import Site
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
    from_ = "Peterbe.com <mail@peterbe.com>"
    body = _get_comment_reply_body(blogcomment.blogitem, blogcomment, parent)
    subject = "Peterbe.com: Reply to your comment"
    send_mail(subject, body, from_, tos)


def _get_comment_reply_body(blogitem, blogcomment, parent):
    base_url = "https://%s" % Site.objects.get_current().domain
    template = loader.get_template("plog/comment_reply_body.txt")
    context = {
        "post": blogitem,
        "comment": blogcomment,
        "parent": parent,
        "base_url": base_url,
    }
    return template.render(context).strip()
