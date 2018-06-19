import datetime

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from django.utils import timezone
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404
from peterbecom.plog.models import BlogItem, Category

from . import serializers
from . import forms

one_year = timezone.now() - datetime.timedelta(days=365)


class InvalidFormFilter(Exception):
    """when the filters are not valid"""


class CategoryViewSet(viewsets.ViewSet):
    def list(self, request):
        all_categories = dict(
            Category.objects.all().values_list('id', 'name')
        )
        one_year = timezone.now() - datetime.timedelta(days=365)
        qs = (
            BlogItem.categories.through.objects
            .filter(blogitem__pub_date__gte=one_year)
            .values('category_id')
            .annotate(Count('category_id'))
            .order_by('-category_id__count')
        )
        choices = []
        _used = set()
        for count in qs:
            pk = count['category_id']
            choices.append(
                {
                    'id': pk,
                    'name': all_categories[pk],
                    'count': count['category_id__count'],
                }
            )
            _used.add(pk)

        category_items = all_categories.items()
        for pk, name in sorted(category_items, key=lambda x: x[1].lower()):
            if pk in _used:
                continue
            choices.append(
                {
                    'id': pk,
                    'name': all_categories[pk],
                    'count': 0,
                }
            )
        serializer = serializers.CategorySerializer(choices, many=True)
        return Response(serializer.data)

        def retrieve(self, request, pk=None):
            raise NotImplementedError(pk)
            # queryset = User.objects.all()
            # user = get_object_or_404(queryset, pk=pk)
            # serializer = UserSerializer(user)
            # return Response(serializer.data)


class IsStaff(BasePermission):

    def has_permission(self, request, view):
        if request.method == 'GET':
            return True
        return (
            request.user and request.user.is_authenticated and
            request.user.is_staff
        )


class BlogitemViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.BlogitemSerializer
    permission_classes = (IsStaff,)

    def get_queryset(self):
        qs = BlogItem.objects.all()
        if self.request.GET.get('since'):
            form = forms.BlogitemsFilterForm(data=self.request.GET)
            if form.is_valid():
                qs = qs.filter(modify_date__gt=form.cleaned_data['since'])
            else:
                raise InvalidFormFilter(form.errors)
        qs = qs.prefetch_related('categories')
        return qs.order_by('-modify_date')

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        latest_blogitem_date = BlogItem.objects.all().aggregate(
            max_modify_date=Max('modify_date')
        )['max_modify_date']

        # category_names = {}
        # for category in Category.objects.all():
        #     category_names[category.id] = category.name
        # categories_map = {}
        # qs = self.get_queryset()
        # for m2m in BlogItem.categories.through.objects.filter(
        #     blogitem__in=qs
        # ):
        #     if m2m.blogitem_id not in categories_map:
        #         categories_map[m2m.blogitem_id] = []
        #     categories_map[m2m.blogitem_id].append(
        #         category_names[m2m.category_id]
        #     )
        # for each in response.data['results']:
        #     each['categories'] = categories_map.get(each['id'], [])

        response.data = {
            'blogitems': response.data,
            'latest_blogitem_date': latest_blogitem_date,
        }
        return response

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        response.data = {
            'blogitem': response.data,
        }
        return response

    def update(self, request, pk=None):
        categories = [
            get_object_or_404(Category, id=x)
            for x in request.data['categories']
        ]
        # This is necessary so that you can send in a list of IDs
        # without the validation failing.
        request.data['categories'] = [
            {'id': category.id, 'name': category.name}
            for category in categories
        ]
        # self.fields['categories'].read_only=True
        response = super().update(request, pk=pk)

        # Manually update the read_only fields
        instance = self.get_object()

        existing = list(instance.categories.all())
        for category in set(categories) - set(existing):
            instance.categories.add(category)
        for category in set(existing) - set(categories):
            instance.categories.remove(category)

        keywords = [x.strip() for x in request.data['keywords'] if x.strip()]
        if instance.proper_keywords != keywords:
            instance.proper_keywords = keywords
            instance.save()
        response.data = {
            'blogitem': response.data,
        }
        return response
