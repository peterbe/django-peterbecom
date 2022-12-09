from django.conf import settings

from paapi5_python_sdk.rest import ApiException
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.partner_type import PartnerType
from paapi5_python_sdk.search_items_request import SearchItemsRequest
from paapi5_python_sdk.get_items_request import GetItemsRequest
from paapi5_python_sdk.search_items_resource import SearchItemsResource


class NothingFoundError(Exception):
    """Happens when you search for something and there are no search results."""


class RateLimitedError(Exception):
    """When the AWS PA API says something like:

    You are submitting requests too quickly.
    Please retry your requests at a slower rate.

    """


"""
# Everything in SearchItemsResource

BrowseNodeInfo.BrowseNodes                         -> BROWSENODEINFO_BROWSENODES
BrowseNodeInfo.BrowseNodes.Ancestor                -> BROWSENODEINFO_BROWSENODES_ANCESTOR
BrowseNodeInfo.BrowseNodes.SalesRank               -> BROWSENODEINFO_BROWSENODES_SALESRANK
BrowseNodeInfo.WebsiteSalesRank                    -> BROWSENODEINFO_WEBSITESALESRANK
Images.Primary.Large                               -> IMAGES_PRIMARY_LARGE
Images.Primary.Medium                              -> IMAGES_PRIMARY_MEDIUM
Images.Primary.Small                               -> IMAGES_PRIMARY_SMALL
Images.Variants.Large                              -> IMAGES_VARIANTS_LARGE
Images.Variants.Medium                             -> IMAGES_VARIANTS_MEDIUM
Images.Variants.Small                              -> IMAGES_VARIANTS_SMALL
ItemInfo.ByLineInfo                                -> ITEMINFO_BYLINEINFO
ItemInfo.Classifications                           -> ITEMINFO_CLASSIFICATIONS
ItemInfo.ContentInfo                               -> ITEMINFO_CONTENTINFO
ItemInfo.ContentRating                             -> ITEMINFO_CONTENTRATING
ItemInfo.ExternalIds                               -> ITEMINFO_EXTERNALIDS
ItemInfo.Features                                  -> ITEMINFO_FEATURES
ItemInfo.ManufactureInfo                           -> ITEMINFO_MANUFACTUREINFO
ItemInfo.ProductInfo                               -> ITEMINFO_PRODUCTINFO
ItemInfo.TechnicalInfo                             -> ITEMINFO_TECHNICALINFO
ItemInfo.Title                                     -> ITEMINFO_TITLE
ItemInfo.TradeInInfo                               -> ITEMINFO_TRADEININFO
Offers.Listings.Availability.MaxOrderQuantity      -> OFFERS_LISTINGS_AVAILABILITY_MAXORDERQUANTITY
Offers.Listings.Availability.Message               -> OFFERS_LISTINGS_AVAILABILITY_MESSAGE
Offers.Listings.Availability.MinOrderQuantity      -> OFFERS_LISTINGS_AVAILABILITY_MINORDERQUANTITY
Offers.Listings.Availability.Type                  -> OFFERS_LISTINGS_AVAILABILITY_TYPE
Offers.Listings.Condition                          -> OFFERS_LISTINGS_CONDITION
Offers.Listings.Condition.SubCondition             -> OFFERS_LISTINGS_CONDITION_SUBCONDITION
Offers.Listings.DeliveryInfo.IsAmazonFulfilled     -> OFFERS_LISTINGS_DELIVERYINFO_ISAMAZONFULFILLED
Offers.Listings.DeliveryInfo.IsFreeShippingEligible -> OFFERS_LISTINGS_DELIVERYINFO_ISFREESHIPPINGELIGIBLE
Offers.Listings.DeliveryInfo.IsPrimeEligible       -> OFFERS_LISTINGS_DELIVERYINFO_ISPRIMEELIGIBLE
Offers.Listings.DeliveryInfo.ShippingCharges       -> OFFERS_LISTINGS_DELIVERYINFO_SHIPPINGCHARGES
Offers.Listings.IsBuyBoxWinner                     -> OFFERS_LISTINGS_ISBUYBOXWINNER
Offers.Listings.LoyaltyPoints.Points               -> OFFERS_LISTINGS_LOYALTYPOINTS_POINTS
Offers.Listings.MerchantInfo                       -> OFFERS_LISTINGS_MERCHANTINFO
Offers.Listings.Price                              -> OFFERS_LISTINGS_PRICE
Offers.Listings.ProgramEligibility.IsPrimeExclusive -> OFFERS_LISTINGS_PROGRAMELIGIBILITY_ISPRIMEEXCLUSIVE
Offers.Listings.ProgramEligibility.IsPrimePantry   -> OFFERS_LISTINGS_PROGRAMELIGIBILITY_ISPRIMEPANTRY
Offers.Listings.Promotions                         -> OFFERS_LISTINGS_PROMOTIONS
Offers.Listings.SavingBasis                        -> OFFERS_LISTINGS_SAVINGBASIS
Offers.Summaries.HighestPrice                      -> OFFERS_SUMMARIES_HIGHESTPRICE
Offers.Summaries.LowestPrice                       -> OFFERS_SUMMARIES_LOWESTPRICE
Offers.Summaries.OfferCount                        -> OFFERS_SUMMARIES_OFFERCOUNT
ParentASIN                                         -> PARENTASIN
RentalOffers.Listings.Availability.MaxOrderQuantity -> RENTALOFFERS_LISTINGS_AVAILABILITY_MAXORDERQUANTITY
RentalOffers.Listings.Availability.Message         -> RENTALOFFERS_LISTINGS_AVAILABILITY_MESSAGE
RentalOffers.Listings.Availability.MinOrderQuantity -> RENTALOFFERS_LISTINGS_AVAILABILITY_MINORDERQUANTITY
RentalOffers.Listings.Availability.Type            -> RENTALOFFERS_LISTINGS_AVAILABILITY_TYPE
RentalOffers.Listings.BasePrice                    -> RENTALOFFERS_LISTINGS_BASEPRICE
RentalOffers.Listings.Condition                    -> RENTALOFFERS_LISTINGS_CONDITION
RentalOffers.Listings.Condition.SubCondition       -> RENTALOFFERS_LISTINGS_CONDITION_SUBCONDITION
RentalOffers.Listings.DeliveryInfo.IsAmazonFulfilled -> RENTALOFFERS_LISTINGS_DELIVERYINFO_ISAMAZONFULFILLED
RentalOffers.Listings.DeliveryInfo.IsFreeShippingEligible -> RENTALOFFERS_LISTINGS_DELIVERYINFO_ISFREESHIPPINGELIGIBLE
RentalOffers.Listings.DeliveryInfo.IsPrimeEligible -> RENTALOFFERS_LISTINGS_DELIVERYINFO_ISPRIMEELIGIBLE
RentalOffers.Listings.DeliveryInfo.ShippingCharges -> RENTALOFFERS_LISTINGS_DELIVERYINFO_SHIPPINGCHARGES
RentalOffers.Listings.MerchantInfo                 -> RENTALOFFERS_LISTINGS_MERCHANTINFO
SearchRefinements                                  -> SEARCHREFINEMENTS
"""


def search(keyword, searchindex="All", item_count=10):
    return _search(keyword=keyword, searchindex=searchindex, item_count=item_count)


def lookup(asin):
    return _search(asin=asin)


def _search(asin=None, keyword=None, searchindex=None, item_count=10):
    assert asin or keyword
    default_api = _get_api()

    # https://webservices.amazon.com/paapi5/documentation/use-cases/organization-of-items-on-amazon/search-index.html
    # search_index = "All"
    # search_index = "Books"

    # https://webservices.amazon.com/paapi5/documentation/search-items.html#resources-parameter
    search_items_resource = _get_search_items_resources()

    if asin:
        get_items_request = GetItemsRequest(
            partner_tag=settings.AWS_ASSOCIATE_TAG,
            partner_type=PartnerType.ASSOCIATES,
            item_ids=[asin],
            resources=search_items_resource,
        )
        try:
            response = default_api.get_items(get_items_request)
        except ApiException as exception:
            if exception.status == 429:
                raise RateLimitedError(exception.reason)
            raise
        if response.items_result:
            for item in response.items_result.items:
                return item.to_dict()
        raise NothingFoundError
    else:
        search_items_request = SearchItemsRequest(
            partner_tag=settings.AWS_ASSOCIATE_TAG,
            partner_type=PartnerType.ASSOCIATES,
            keywords=keyword,
            search_index=searchindex,
            item_count=item_count,
            resources=search_items_resource,
        )
        response = default_api.search_items(search_items_request)
        products = []
        for search_result in response.search_result.items:
            products.append(search_result.to_dict())
        return products


def _get_api():
    return DefaultApi(
        access_key=settings.AWS_PAAPI_ACCESS_KEY,
        secret_key=settings.AWS_PAAPI_ACCESS_SECRET,
        host="webservices.amazon.com",
        region="us-east-1",
    )


def _get_search_items_resources():
    return [
        SearchItemsResource.ITEMINFO_TITLE,
        SearchItemsResource.ITEMINFO_PRODUCTINFO,
        SearchItemsResource.ITEMINFO_TECHNICALINFO,
        SearchItemsResource.ITEMINFO_FEATURES,
        SearchItemsResource.ITEMINFO_CLASSIFICATIONS,
        SearchItemsResource.ITEMINFO_BYLINEINFO,
        SearchItemsResource.ITEMINFO_CONTENTINFO,
        SearchItemsResource.IMAGES_PRIMARY_LARGE,
        SearchItemsResource.IMAGES_PRIMARY_MEDIUM,
        # SearchItemsResource.IMAGES_PRIMARY_SMALL,
        SearchItemsResource.OFFERS_LISTINGS_PRICE,
    ]
