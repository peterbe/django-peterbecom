from django.contrib import admin
from models import BlogItem, BlogComment


def truncate_text(text, characters):
    if len(text) > characters:
        text = text[: characters - 1] + "\u2026"
    return text


class BlogItemAdmin(admin.ModelAdmin):
    list_display = ("title", "oid", "pub_date")
    ordering = ("-pub_date",)


class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ("oid", "blogitem_summary", "summary", "approved", "add_date")
    ordering = ("-add_date",)
    list_select_related = True  # Why does this not work?!

    def blogitem_summary(self, obj):
        return '<a href="#">%s</a>' % truncate_text(obj.blogitem.title, 28)

    blogitem_summary.allow_tags = True

    def summary(self, obj):
        out = []
        if obj.name or obj.email:
            out.append("By:")
        if obj.name:
            out.append(obj.name)
        if obj.email:
            out.append("(%s)" % obj.email)
        text = truncate_text(obj.comment, 50)
        out.append(text)
        return " ".join(out)


admin.site.register(BlogItem, BlogItemAdmin)
admin.site.register(BlogComment, BlogCommentAdmin)
