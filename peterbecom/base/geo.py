from functools import lru_cache

from django.contrib.gis.geoip2 import GeoIP2
from geoip2.errors import AddressNotFoundError

# temporary
from django.conf import settings
import os

assert settings.GEOIP_PATH
print(os.listdir(os.path.dirname(settings.GEOIP_PATH)))
print(
    os.path.basename(settings.GEOIP_PATH)
    in os.listdir(os.path.dirname(settings.GEOIP_PATH))
)
assert os.path.isfile(settings.GEOIP_PATH), settings.GEOIP_PATH


# geoip_looker_upper = None
geoip_looker_upper = GeoIP2()


@lru_cache()
def ip_to_city(ip_address):
    if ip_address == "127.0.0.1":
        return
    # Initialize late
    # global geoip_looker_upper
    # if geoip_looker_upper is None:
    #     geoip_looker_upper = GeoIP2()
    try:
        return geoip_looker_upper.city(ip_address)
    except AddressNotFoundError:
        return
