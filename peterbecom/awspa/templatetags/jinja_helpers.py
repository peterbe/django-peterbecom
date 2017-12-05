from django_jinja import library
from django.template.loader import render_to_string


@library.global_function
def awspa_product(awsproduct, show_action_button=False, hide_image=False):

    def _fix_item(item):
        for key in ('Feature', 'Author'):
            if (
                item['ItemAttributes'].get(key) and
                isinstance(item['ItemAttributes'][key], str)
            ):
                item['ItemAttributes'][key] = [
                    item['ItemAttributes'][key]
                ]

    item = awsproduct.payload
    _fix_item(item)

    if not item['ItemAttributes'].get('ListPrice'):
        print("SKIPPING BECAUSE NO LIST PRICE")
        print(item)
        # awsproduct.delete()
        return ''

    # if not item['ItemAttributes'].get('Binding'):
    #     from pprint import pprint
    #     print("ITEM")
    #     pprint(item)
    #     print('-'* 100)

    html = render_to_string('awspa/item.html', {
        'awsproduct': awsproduct,
        'item': item,
        'title': awsproduct.title,
        'asin': awsproduct.asin,
        'keyword': awsproduct.keyword,
        'searchindex': awsproduct.searchindex,
        'show_action_button': show_action_button,
        'hide_image': hide_image,
    })
    return html


@library.global_function
def show_keyword_count(blogitem, keyword_count):
    counts = []
    for keyword in blogitem.get_all_keywords():
        count = keyword_count.get(keyword)
        if count is not None:
            counts.append(count)
    sum_ = sum(counts)
    first = ' + '.join(str(x) for x in counts)
    return first + ' = ' + str(sum_)
