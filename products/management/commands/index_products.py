from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Product
from products.search.elasticsearch_utils import ElasticsearchUtils

class Command(BaseCommand):
    help = 'Bulk index all products from the database to Elasticsearch'

    def handle(self, *args, **kwargs):
        es_utils = ElasticsearchUtils()
        index_name = "slash_products"

        self.stdout.write("Checking index...")

        if es_utils.index_exists(index_name):
            self.stdout.write("Index exists. Deleting and recreating...")
            es_utils.delete_index(index_name)
        es_utils.create_product_index()

        self.stdout.write("Fetching products from database...")
        products = Product.objects.filter(is_active=True).select_related('category').prefetch_related('product_images')
        
        count = products.count()
        self.stdout.write(f"Found {count} products. Starting bulk index...")

        success = es_utils.bulk_index_data(index_name, list(products))

        if success:
            self.stdout.write(self.style.SUCCESS(f"Successfully indexed {count} products at {timezone.now()}"))
        else:
            self.stdout.write(self.style.ERROR("Bulk indexing failed. Check logs."))