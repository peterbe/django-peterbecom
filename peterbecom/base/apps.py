from django.apps import AppConfig
from django.conf import settings
from elasticsearch_dsl.connections import connections


class BaseConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "peterbecom.base"

    def ready(self):
        connections.configure(**settings.ES_CONNECTIONS)
