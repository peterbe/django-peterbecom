from django.conf import settings
from django.template import loader
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from huey.contrib.djhuey import task

from peterbecom.plog.models import BlogComment


@task()
def send_new_comment_email(blogcomment_id):
    print("SEND_NEW_COMMENT_EMAIL", repr(blogcomment_id))
    blogcomment = BlogComment.objects.get(id=blogcomment_id)
    tos = [x[1] for x in settings.MANAGERS]
    from_ = ["%s <%s>" % x for x in settings.MANAGERS][0]
    body = _get_comment_body(blogcomment.blogitem, blogcomment)
    subject = "Peterbe.com: New comment on '{}'".format(blogcomment.blogitem.title)
    send_mail(subject, body, from_, tos)


def _get_comment_body(blogitem, blogcomment):
    base_url = "https://%s" % Site.objects.get_current().domain
    if "peterbecom.local" in base_url:
        base_url = "http://localhost:4000"
    admin_url = base_url.replace("www.", "admin.")
    template = loader.get_template("plog/comment_body.txt")
    context = {
        "post": blogitem,
        "comment": blogcomment,
        "base_url": base_url,
        "admin_url": admin_url,
    }
    return template.render(context).strip()
