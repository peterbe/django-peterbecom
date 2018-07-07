from rest_framework import serializers
from peterbecom.plog.models import BlogItem, Category, BlogComment


class SimpleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("name", "id")


class CategorySerializer(serializers.Serializer):
    name = serializers.CharField()
    id = serializers.IntegerField()
    count = serializers.IntegerField()

    class Meta:
        fields = ("name", "id", "count")


class BlogitemSerializer(serializers.HyperlinkedModelSerializer):
    _url = serializers.HyperlinkedIdentityField(
        view_name="api:blogitem-detail", lookup_field="pk"
    )
    categories = SimpleCategorySerializer(many=True, read_only=True)
    keywords = serializers.ListSerializer(
        source="proper_keywords",
        child=serializers.CharField(max_length=200),
        read_only=True,
    )

    def __init__(self, *args, **kwargs):
        super(BlogitemSerializer, self).__init__(*args, **kwargs)
        if isinstance(self.instance, BlogItem):
            # Individual blogitem endpoint!
            pass
        else:
            self.fields.pop("text")
            self.fields.pop("text_rendered")

        optionals = ("url", "summary", "codesyntax")
        for key in optionals:
            self.fields[key].required = False
            self.fields[key].allow_blank = True

    class Meta:
        model = BlogItem
        fields = (
            "id",
            "_url",
            "url",
            "oid",
            "title",
            "pub_date",
            "categories",
            "text",
            "text_rendered",
            "summary",
            "display_format",
            "keywords",
            "codesyntax",
            "disallow_comments",
            "hide_comments",
            "modify_date",
            "plogrank",
        )
        read_only_fields = ("modify_date", "text_rendered", "plogrank")


class CommentSerializer(serializers.HyperlinkedModelSerializer):
    _url = serializers.HyperlinkedIdentityField(
        view_name="api:comment-detail", lookup_field="pk"
    )
    _blogitem_url = serializers.HyperlinkedIdentityField(
        view_name="api:blogitem-detail", lookup_field="pk"
    )

    def __init__(self, *args, **kwargs):
        super(CommentSerializer, self).__init__(*args, **kwargs)
        # if isinstance(self.instance, BlogItem):
        #     # Individual blogitem endpoint!
        #     pass
        # else:
        #     self.fields.pop('text')
        #     self.fields.pop('text_rendered')

        optionals = ()
        for key in optionals:
            self.fields[key].required = False
            self.fields[key].allow_blank = True

    class Meta:
        model = BlogComment
        fields = (
            "id",
            "_url",
            "oid",
            "blogitem_id",
            "_blogitem_url",
            # "parent",
            "add_date",
            "approved",
            "comment",
            "comment_rendered",
            "name",
            "email",
        )
        read_only_fields = ("add_date", "comment_rendered")
