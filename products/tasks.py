import os
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import ProductImage, CategoryImage, ProductSearchLog, Product, ProductViewLog
from .ml_models.collab_filter import CollaborativeFilteringModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

User = get_user_model()

THUMB_SIZE = (150, 150)
MEDIUM_SIZE = (600, 600)
MODEL_FILEPATH = '/tmp/recommendation_model.pkl'


def resize_image(image_field, size):
    """Resize an image to the given size and return a ContentFile."""
    img = Image.open(image_field)
    img.thumbnail(size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    fmt = img.format if img.format else 'JPEG'
    img.save(buffer, format=fmt)
    return ContentFile(buffer.getvalue())


@shared_task
def generate_image_thumbnails(model_name, instance_id):
    """Generate thumb and medium images for ProductImage or CategoryImage."""
    model = ProductImage if model_name == 'ProductImage' else CategoryImage
    try:
        instance = model.objects.get(id=instance_id)
    except model.DoesNotExist:
        return

    if not instance.image_large:
        return

    if not instance.image_thumb:
        instance.image_thumb.save(
            f"thumb_{os.path.basename(instance.image_large.name)}",
            resize_image(instance.image_large, THUMB_SIZE),
            save=False
        )

    if not instance.image_medium:
        instance.image_medium.save(
            f"medium_{os.path.basename(instance.image_large.name)}",
            resize_image(instance.image_large, MEDIUM_SIZE),
            save=False
        )

    instance.save(update_fields=['image_thumb', 'image_medium'])


@shared_task
def log_product_search_task(query, user_id=None, country_id=None):
    """Create a ProductSearchLog entry asynchronously."""
    log_entry = ProductSearchLog(query=query)
    if user_id:
        try:
            log_entry.user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass
    if country_id:
        log_entry.country_id = country_id
    log_entry.save()


@shared_task
def index_product_to_elasticsearch(product_id):
    from .search.elasticsearch_utils import ElasticsearchUtils
    es_utils = ElasticsearchUtils()
    
    product = Product.objects.prefetch_related('product_images').filter(id=product_id).first()
    
    if not product:
        return

    document = es_utils.convert_product_to_document(product)
    
    if len(document.get("image_features", [])) != 512:
        logging.error(f"Skipping indexing for {product_id}: Image features invalid.")
        return

    es_utils.index_data("slash_products", document)


@shared_task(bind=True)
def train_recommendation_model(self):
    try:
        logger.info("Starting recommendation model training...")

        view_logs = ProductViewLog.objects.filter(
            user__isnull=False
        ).values_list('user_id', 'product_id')

        interactions = [(str(uid), str(pid)) for uid, pid in view_logs]

        if len(interactions) < 10:
            logger.warning("Insufficient interactions to train model")
            return {
                "status": "skipped",
                "reason": "insufficient_interactions",
                "count": len(interactions)
            }

        logger.info(f"Training on {len(interactions)} interactions...")

        model = CollaborativeFilteringModel(factors=50, iterations=10)
        train_result = model.train(interactions)

        if train_result["status"] != "success":
            logger.error(f"Training failed: {train_result}")
            return train_result

        if model.save(MODEL_FILEPATH):
            logger.info(f"Model saved to {MODEL_FILEPATH}")
            stats = model.get_model_stats()
            logger.info(f"Model stats: {stats}")

            try:
                from .views import invalidate_recommendation_model_cache
                invalidate_recommendation_model_cache()
                logger.info("In-process model cache invalidated.")
            except Exception as cache_err:
                logger.warning(f"Could not invalidate model cache: {cache_err}")

            return {
                "status": "success",
                "message": "Model trained and saved",
                "stats": stats,
                "timestamp": timezone.now().isoformat()
            }
        else:
            logger.error("Failed to save model")
            return {"status": "failed", "reason": "save_error"}

    except Exception as e:
        logger.error(f"Error during model training: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@shared_task(bind=True)
def test_recommendation_model(self):
    try:
        model = CollaborativeFilteringModel.load(MODEL_FILEPATH)

        if not model:
            return {"status": "error", "message": "Model not found"}

        test_user = User.objects.filter(product_views__isnull=False).first()

        if not test_user:
            return {"status": "no_test_user"}

        recommendations = model.get_recommendations(
            user_id=test_user.id,
            num_recommendations=5
        )

        stats = model.get_model_stats()

        return {
            "status": "success",
            "test_user_id": str(test_user.id),
            "recommendations_count": len(recommendations),
            "recommendations": recommendations[:5],
            "model_stats": stats
        }

    except Exception as e:
        logger.error(f"Error testing model: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }