from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Profile, Document, KYCVerification
from authentication.utils import send_kyc_status_email

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

@receiver(pre_save, sender=User)
def track_user_deactivation(sender, instance, **kwargs):
    """
    Automatically set/clear deactivated_at on Profile when is_active is toggled.
    """
    if instance.pk:
        try:
            previous = User.objects.get(pk=instance.pk)
            # If they were active and are now deactivated, set deactivated_at
            if previous.is_active and not instance.is_active:
                if hasattr(instance, 'profile'):
                    instance.profile.deactivated_at = timezone.now()
            # If they were deactivated and are now activated, clear deactivated_at
            elif not previous.is_active and instance.is_active:
                if hasattr(instance, 'profile'):
                    instance.profile.deactivated_at = None
        except User.DoesNotExist:
            pass

@receiver(post_save, sender=Document)
def create_new_verification_request(sender, instance, **kwargs):
    """
    When documents are uploaded or updated, create a NEW verification request 
    to maintain history, but only if one is not already PENDING and ALL documents are present.
    """
    required_fields = [
        'identification_document_front',
        'identification_document_back',
        'selfie',
        'proof_of_address'
    ]
    
    is_complete = all(getattr(instance, field) for field in required_fields)

    if is_complete and not KYCVerification.objects.filter(profile=instance.profile, status='PENDING').exists():
        KYCVerification.objects.create(
            profile=instance.profile,
            status='PENDING'
        )

@receiver(pre_save, sender=KYCVerification)
def capture_previous_status(sender, instance, **kwargs):
    """
    Capture the status before saving to detect changes.
    """
    if instance.pk:
        instance._previous_status = KYCVerification.objects.get(pk=instance.pk).status
    else:
        instance._previous_status = None

@receiver(post_save, sender=KYCVerification)
def handle_verification_status_change(sender, instance, created, **kwargs):
    """
    1. Update Profile.is_complete and kyc_level based on the LATEST verification status.
    2. Send email notification when status changes from PENDING to APPROVED/REJECTED.
    """
    profile = instance.profile
    latest = profile.latest_verification

    # Only update profile based on the latest record
    if latest and latest.pk == instance.pk:
        if instance.status == 'APPROVED':
            profile.kyc_level = 'enhanced'
            if not profile.is_complete:
                profile.is_complete = True
            profile.save()
        else:
            if profile.is_complete:
                profile.is_complete = False
                profile.save()

    # Email Notification Logic
    previous_status = getattr(instance, '_previous_status', None)
    
    if instance.status != 'PENDING' and instance.status != previous_status:
        send_kyc_status_email(
            user=profile.user,
            status=instance.status,
            notes=instance.admin_notes
        )
