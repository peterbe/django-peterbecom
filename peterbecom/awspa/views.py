from django import http
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string

from .models import AWSProduct
from .search import search


@login_required
def search_new(request):
    context = {}
    keyword = request.GET.get('keyword')
    searchindex = request.GET.get('searchindex', 'All')
    items, error = search(keyword, searchindex=searchindex, sleep=1)
    if error:
        context['error'] = error
    else:
        from pprint import pprint
        context['cards'] = []
        # existing_awsproducts = AWSProduct.objects.filter(
        #     keyword=keyword,
        #     searchindex=searchindex,
        # )
        # known_asins = set()
        # for awsproduct in existing_awsproducts:
        #     known_asins.add(awsproduct.asin)

        for item in items:
            item.pop('ImageSets', None)
            # print('=' * 100)
            # pprint(item)
            asin = item['ASIN']
            title = item['ItemAttributes']['Title']
            if not item['ItemAttributes'].get('ListPrice'):
                print("SKIPPING BECAUSE NO LIST PRICE")
                print(item)
                continue
            # print(title)
            try:
                awsproduct = AWSProduct.objects.get(
                    asin=asin,
                    keyword=keyword,
                    searchindex=searchindex,
                )
                awsproduct.title = title
                awsproduct.payload = item
                awsproduct.save()
            except AWSProduct.DoesNotExist:
                awsproduct = AWSProduct.objects.create(
                    asin=asin,
                    title=title,
                    payload=item,
                    keyword=keyword,
                    searchindex=searchindex,
                )

            # if asin in known_asins:
            #     continue

            # Hacks!
            if item['ItemAttributes'].get('Author'):
                if isinstance(item['ItemAttributes']['Author'], str):
                    item['ItemAttributes']['Author'] = [
                        item['ItemAttributes']['Author']
                    ]

            if not item.get('MediumImage'):
                print("SKIPPING")
                pprint(item)
                print('...BECAUSE NO MediumImage')
                continue

            html = render_to_string('awspa/item.html', {
                'awsproduct': awsproduct,
                'item': item,
                'title': title,
                'asin': asin,
                'keyword': keyword,
                'searchindex': searchindex,
                'show_action_button': True,
            })
            context['cards'].append(html)

    return http.JsonResponse(context)
