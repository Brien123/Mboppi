from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
from authentication.models import OTP
from django.core.files.uploadedfile import SimpleUploadedFile
import io
from PIL import Image

User = get_user_model()

class AuthenticationTests(APITestCase):
    def setUp(self):
        self.signup_url = reverse('signup')
        self.otp_verify_url = reverse('otp-verify')
        self.login_url = reverse('login')
        self.otp_send_url = reverse('otp-send')
        self.email = "testuser@example.com"
        self.password = "YourSecurePassword123"
        self.phone = "+1234567890"
        
        # Create a small dummy image for avatar
        file_obj = io.BytesIO()
        image = Image.new('RGB', (100, 100), color=(73, 109, 137))
        image.save(file_obj, 'jpeg')
        file_obj.seek(0)
        self.avatar = SimpleUploadedFile('avatar.jpg', file_obj.read(), content_type='image/jpeg')

    def test_registration_flow(self):
        """Test user registration and OTP generation."""
        data = {
            "email": self.email,
            "first_name": "John",
            "last_name": "Doe",
            "password": self.password,
            "phone": self.phone,
            "avatar": self.avatar
        }
        
        response = self.client.post(self.signup_url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(email=self.email)
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.profile.avatar)
        
        # Check if OTP was created
        otp = OTP.objects.filter(email=self.email).first()
        self.assertIsNotNone(otp)
        
        # Check if email was "sent" (captured in mail outbox)
        # Note: In tests, emails are sent to django.core.mail.outbox
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(otp.code, mail.outbox[0].body)

    def test_otp_verification_flow(self):
        """Test OTP verification and user activation."""
        # 1. Register first
        user = User.objects.create_user(
            username="testuser",
            email=self.email,
            password=self.password,
            first_name="John",
            last_name="Doe",
            is_active=False
        )
        otp = OTP.generate_otp(self.email)
        
        # 2. Verify with wrong code
        response = self.client.post(self.otp_verify_url, {
            "email": self.email,
            "code": "000000"
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # 3. Verify with correct code
        response = self.client.post(self.otp_verify_url, {
            "email": self.email,
            "code": otp.code
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIn('access', response.data['data'])
        self.assertIn('refresh', response.data['data'])

    def test_login_flow(self):
        """Test login success and failure cases."""
        # 1. Unverified user login
        user = User.objects.create_user(
            username="unverified",
            email=self.email,
            password=self.password,
            is_active=False
        )
        response = self.client.post(self.login_url, {
            "email": self.email,
            "password": self.password
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # 2. Verified user login
        user.is_active = True
        user.save()
        response = self.client.post(self.login_url, {
            "email": self.email,
            "password": self.password
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['data'])

    def test_otp_resend(self):
        """Test resending OTP."""
        User.objects.create_user(
            username="resenduser",
            email=self.email,
            password=self.password
        )
        response = self.client.post(self.otp_send_url, {"email": self.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(OTP.objects.filter(email=self.email).count(), 1)


class DeactivationTests(APITestCase):
    def test_deactivation_flow_and_deactivated_at_field(self):
        """Test that deactivation sets deactivated_at and reactivation clears it."""
        user = User.objects.create_user(
            username="deactuser",
            email="deact@example.com",
            password="password123",
            is_active=True
        )
        self.assertIsNone(user.profile.deactivated_at)

        # Deactivate user
        user.is_active = False
        user.save()
        user.profile.refresh_from_db()
        self.assertIsNotNone(user.profile.deactivated_at)
        
        # Reactivate user
        user.is_active = True
        user.save()
        user.profile.refresh_from_db()
        self.assertIsNone(user.profile.deactivated_at)

    def test_delete_user_account_after_30_days_of_deactivation_task(self):
        """Test the Celery task only deletes users deactivated > 30 days ago."""
        from django.utils import timezone
        from datetime import timedelta
        from authentication.tasks import delete_user_account_after_30_days_of_deactivation

        # 1. Unverified user (is_active=False, deactivated_at=None, created > 30 days ago)
        unverified_user = User.objects.create_user(
            username="unverified",
            email="unverified@example.com",
            password="password123",
            is_active=False
        )
        unverified_user.profile.created_at = timezone.now() - timedelta(days=40)
        unverified_user.profile.save()

        # 2. Recently deactivated user (is_active=False, deactivated_at = 5 days ago)
        recently_deactivated = User.objects.create_user(
            username="recent",
            email="recent@example.com",
            password="password123",
            is_active=True
        )
        recently_deactivated.is_active = False
        recently_deactivated.save()
        recently_deactivated.profile.deactivated_at = timezone.now() - timedelta(days=5)
        recently_deactivated.profile.save()

        # 3. Long-term deactivated user (is_active=False, deactivated_at = 35 days ago)
        long_term_deactivated = User.objects.create_user(
            username="longterm",
            email="longterm@example.com",
            password="password123",
            is_active=True
        )
        long_term_deactivated.is_active = False
        long_term_deactivated.save()
        long_term_deactivated.profile.deactivated_at = timezone.now() - timedelta(days=35)
        long_term_deactivated.profile.save()

        # Run the celery task
        delete_user_account_after_30_days_of_deactivation()

        # Long-term deactivated user should be deleted
        self.assertFalse(User.objects.filter(id=long_term_deactivated.id).exists())

        # Unverified user and recently deactivated user should still exist
        self.assertTrue(User.objects.filter(id=unverified_user.id).exists())
        self.assertTrue(User.objects.filter(id=recently_deactivated.id).exists())
