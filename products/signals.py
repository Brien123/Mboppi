import django.dispatch
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from .models import ProductImage, CategoryImage, Product
from .tasks import generate_image_thumbnails, log_product_search_task, index_product_to_elasticsearch
from .search.elasticsearch_utils import ElasticsearchUtils
from django.db import transaction
from django.core.cache import cache

# Custom signal for search logging
product_search_performed = django.dispatch.Signal()


@receiver(post_save, sender=ProductImage)
@receiver(post_save, sender=CategoryImage)
def trigger_thumbnail_generation(sender, instance, created, **kwargs):
    """When a ProductImage or CategoryImage is saved, generate thumbnails via Celery."""
    if instance.image_large and (not instance.image_thumb or not instance.image_medium):
        generate_image_thumbnails.delay(sender.__name__, instance.id)

@receiver([post_save, post_delete], sender=Product)
def trigger_product_indexing(sender, instance, **kwargs):
    """
    Handles indexing with task deduplication and atomic transaction safety.
    """
    if kwargs.get('signal') == post_delete:
        ElasticsearchUtils().delete_index_data("slash_products", str(instance.id))
        return
    lock_id = f"indexing-lock-{instance.id}"
    if cache.get(lock_id):
        return

    cache.set(lock_id, True, timeout=5)
    transaction.on_commit(
        lambda: index_product_to_elasticsearch.delay(instance.id)
    )

@receiver([post_save, post_delete], sender=ProductImage)
def trigger_product_reindex_on_image_change(sender, instance, **kwargs):
    """
    When an image is added/deleted, re-index the parent product 
    to update image_features vectors.
    """
    if instance.product:
        transaction.on_commit(
            lambda: index_product_to_elasticsearch.delay(instance.product.id)
        )


@receiver(product_search_performed)
def handle_product_search(sender, query, user, country, **kwargs):
    """Log product searches asynchronously."""
    log_product_search_task.delay(query=query,user_id=user.id if user and user.is_authenticated else None,country_id=country.id if country else None)