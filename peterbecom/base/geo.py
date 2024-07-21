from functools import lru_cache

from django.contrib.gis.geoip2 import GeoIP2, HAS_GEOIP2
from geoip2.errors import AddressNotFoundError

assert HAS_GEOIP2
geoip_looker_upper = GeoIP2()


@lru_cache()
def ip_to_city(ip_address):
    if ip_address == "127.0.0.1":
        return
    try:
        return geoip_looker_upper.city(ip_address)
    except AddressNotFoundError:
        return


@lru_cache()
def ip_to_country_code(ip_address):
    if ip_address == "127.0.0.1":
        return
    try:
        return geoip_looker_upper.country_code(ip_address)
    except AddressNotFoundError:
        return
