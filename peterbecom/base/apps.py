from elasticsearch_dsl.connections import connections

from django.conf import settings
from django.apps import AppConfig


class BaseConfig(AppConfig):
    name = "peterbecom.base"

    def ready(self):
        connections.configure(**settings.ES_CONNECTIONS)
