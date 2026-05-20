from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

@shared_task
def delete_user_account_after_30_days_of_deactivation():
    cutoff = timezone.now() - timezone.timedelta(days=30)
    deactivated_users = User.objects.filter(
        is_active=False, 
        profile__deactivated_at__lt=cutoff
    )
    deactivated_users.delete()