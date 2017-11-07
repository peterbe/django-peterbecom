# from elasticsearch.exceptions import ConnectionError
from elasticsearch_dsl.connections import connections

from django.conf import settings
from django.apps import AppConfig
# from django.core.exceptions import ImproperlyConfigured


class BaseConfig(AppConfig):
    name = 'peterbecom.base'

    def ready(self):
        connections.configure(**settings.ES_CONNECTIONS)

    #     try:
    #         self._check_es_version()
    #     except ConnectionError:
    #         import time
    #         time.sleep(5)
    #         self._check_es_version()
    #
    # @staticmethod
    # def _check_es_version():
    #     es = connections.get_connection()
    #     version = es.info()['version']['number']
    #     if version < '4' or version >= '6':
    #         raise ImproperlyConfigured('Require ES version 5.x.x')
