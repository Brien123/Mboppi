from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=15, blank=True)
    is_complete = models.BooleanField(default=False)
    birth_date = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    country = models.ForeignKey('common.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    @property
    def is_kyc_verified(self)->bool:
        return self.kyc_level != 'none'

    @property
    def latest_verification(self):
        return self.verifications.order_by('-pk').first()

    KYC_LEVEL_CHOICES = (
        ('none', _('None')),
        ('basic', _('Basic')),
        ('enhanced', _('Enhanced')),
    )
    kyc_level = models.CharField(max_length=20, choices=KYC_LEVEL_CHOICES, default='none')

    KYC_BASIC_LIMIT_USD = 100
    KYC_ENHANCED_LIMIT_USD = 50000

    @property
    def kyc_spending_limit_usd(self) -> int:
        if self.kyc_level == 'none':
            return 0
        if self.kyc_level == 'basic':
            return self.KYC_BASIC_LIMIT_USD
        return self.KYC_ENHANCED_LIMIT_USD

class Document(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='documents')
    identification_document_front = models.ImageField(upload_to='documents/', null=True, blank=True)
    identification_document_back = models.ImageField(upload_to='documents/', null=True, blank=True)
    selfie = models.ImageField(upload_to='selfies/', null=True, blank=True)
    proof_of_address = models.ImageField(upload_to='proof_of_address/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.profile.user.username}'s documents"

class KYCVerification(models.Model):
    STATUS_CHOICES = (
        ('PENDING', _('Pending')),
        ('APPROVED', _('Approved')),
        ('REJECTED', _('Rejected')),
    )

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='verifications')
    status = models.CharField(_('Status'), max_length=10, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(_('Admin Notes'), blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_kycs')
    reviewed_at = models.DateTimeField(_('Reviewed At'), null=True, blank=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('KYC Verification')
        verbose_name_plural = _('KYC Verifications')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.profile.user.username} - {self.get_status_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

class BasicKYCSubmission(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='basic_kyc')
    full_name = models.CharField(max_length=255)
    birth_date = models.DateField()
    nationality = models.CharField(max_length=100)
    occupation = models.CharField(max_length=255)
    source_of_funds = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Basic KYC for {self.profile.user.username}"