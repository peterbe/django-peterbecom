from django_jinja import library
from django.template.loader import render_to_string


@library.global_function
def awspa_product(awsproduct, show_action_button=False, hide_image=False):

    item = awsproduct.payload

    if awsproduct.paapiv5:
        if not item.get("offers"):
            print("SKIPPING BECAUSE NO offers")
            print(repr(awsproduct))
            return ""

        try:
            item["title"] = item["item_info"]["title"]["display_value"]
            item["display_price"] = item["offers"]["listings"][0]["price"][
                "display_amount"
            ]
            item["medium_image"] = item["images"]["primary"]["medium"]["url"]
            by_line_info = item["item_info"].get("by_line_info") or {}
            item["authors"] = [x["name"] for x in by_line_info.get("contributors", [])]
            item["brand"] = (by_line_info.get("brand") or {}).get("display_value")
            item["category"] = item["item_info"]["classifications"]["product_group"][
                "display_value"
            ]
        except Exception:
            from pprint import pprint

            print("PROBLEM WITH SHORTCUTS!...")
            print(repr(awsproduct))
            pprint(item)
            print()
            raise
    else:

        def _fix_item(item):
            for key in ("Feature", "Author"):
                if item["ItemAttributes"].get(key) and isinstance(
                    item["ItemAttributes"][key], str
                ):
                    item["ItemAttributes"][key] = [item["ItemAttributes"][key]]

        _fix_item(item)

        if not item["ItemAttributes"].get("ListPrice"):
            print("SKIPPING BECAUSE NO LIST PRICE")
            print(item)
            # awsproduct.delete()
            return ""

        if not item.get("MediumImage"):
            print("SKIPPIING BECAUSE NO MediumImage")
            print(item)
            return ""

    html = render_to_string(
        "awspa/item.html",
        {
            "awsproduct": awsproduct,
            "item": item,
            "title": awsproduct.title,
            "asin": awsproduct.asin,
            "keyword": awsproduct.keyword,
            "searchindex": awsproduct.searchindex,
            "show_action_button": show_action_button,
            "hide_image": hide_image,
        },
    )
    return html


@library.global_function
def show_keyword_count(blogitem, keyword_count):
    counts = []
    for keyword in blogitem.get_all_keywords():
        count = keyword_count.get(keyword)
        if count is not None:
            counts.append(count)
    sum_ = sum(counts)
    first = " + ".join(str(x) for x in counts)
    return first + " = " + str(sum_)
