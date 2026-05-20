import elasticsearch
from django.conf import settings

class ElasticsearchClient:
    def __init__(self):
        host = settings.ELASTICSEARCH_HOST.replace("http://", "").replace("https://", "")
        host = host.split(":")[0]

        self.client = elasticsearch.Elasticsearch(
            hosts=[{"host": host, "port": 9200, "scheme": "http"}],
            basic_auth=(settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD),
        )

    def ping(self):
        return self.client.ping()