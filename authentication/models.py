from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.utils.translation import gettext_lazy as _
import random

class OTP(models.Model):
    email = models.EmailField(_('email address'))
    code = models.CharField(_('OTP code'), max_length=6)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    is_verified = models.BooleanField(_('is verified'), default=False)

    class Meta:
        verbose_name = _('OTP')
        verbose_name_plural = _('OTPs')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} - {self.code}"

    def is_valid(self):
        return timezone.now() < self.created_at + timedelta(minutes=10)

    @classmethod
    def generate_otp(cls, email):
        cls.objects.filter(email=email, is_verified=False).delete()
        code = str(random.randint(100000, 999999))
        otp = cls.objects.create(email=email, code=code)
        return otp
