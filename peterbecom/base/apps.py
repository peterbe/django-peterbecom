from elasticsearch_dsl.connections import connections

from django.conf import settings
from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class BaseConfig(AppConfig):
    name = 'peterbecom.base'

    def ready(self):
        connections.configure(**settings.ES_CONNECTIONS)
        es = connections.get_connection()
        version = es.info()['version']['number']
        if version < '4' or version >= '6':
            raise ImproperlyConfigured('Require ES version 5.x.x')
