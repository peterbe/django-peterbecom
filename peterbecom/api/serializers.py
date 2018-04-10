from rest_framework import serializers
from peterbecom.plog.models import BlogItem, Category


# class CategoriesField(serializers.Field):
#     def to_representation(self, obj):
#         return [
#             {'id': x.id, 'name': x.name}
#             for x in obj.categories.all()
#         ]
#
#     def to_internal_value(self, data):
#         raise Exception(data)
#         data = data.strip('rgb(').rstrip(')')
#         red, green, blue = [int(col) for col in data.split(',')]
#         return Color(red, green, blue)


class SimpleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('name', 'id')

    # def to_representation(self, obj):
    #     print(dir(self))
    #     # print(self.context)
    #     print(self.context['view']._list_of_things)
    #     return 'xxx'
    #     # print(self.root)
    #     # print(self.__class__)
    #     raise Exception
    #     # print(repr(obj))
    #
    #     return "to_representation"


# class SimpleCategorySerializer(serializers.ModelSerializer):
#
#     class Meta:
#         model = Category
#         fields = ('name', 'id')
#
#     def to_representation(self, obj):
#         print(dir(self))
#         # print(self.context)
#         print(self.context['view']._list_of_things)
#         return 'xxx'
#         # print(self.root)
#         # print(self.__class__)
#         raise Exception
#         # print(repr(obj))
#
#         return "to_representation"
#

class CategorySerializer(serializers.Serializer):
    name = serializers.CharField()
    id = serializers.IntegerField()
    count = serializers.IntegerField()

    class Meta:
        fields = ('name', 'id', 'count')


class BlogitemSerializer(serializers.HyperlinkedModelSerializer):
    # categories = CategoriesField(source='*')
    _url = serializers.HyperlinkedIdentityField(
        view_name='api:blogitem-detail',
        lookup_field='pk'
    )
    categories = SimpleCategorySerializer(many=True)
    keywords = serializers.ListSerializer(
        source='proper_keywords',
        child=serializers.CharField(min_length=200)
    )

    def __init__(self, *args, **kwargs):
        super(BlogitemSerializer, self).__init__(*args, **kwargs)
        if isinstance(self.instance, BlogItem):
            # Detail !
            pass
        else:
            self.fields.pop('text')
            self.fields.pop('text_rendered')

    class Meta:
        model = BlogItem
        fields = (
            'id',
            '_url',
            'url',
            'oid',
            'title',
            'pub_date',
            'categories',
            'text',
            'text_rendered',
            'summary',
            'display_format',
            'keywords',
            'codesyntax',
            'disallow_comments',
            'hide_comments',
            'modify_date',
            'plogrank',
        )
        read_only_fields = (
            'modify_date',
            'text_rendered',
            'plogrank',
        )
