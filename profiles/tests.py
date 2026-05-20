from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from .models import Profile, Document, KYCVerification, BasicKYCSubmission
import io
from PIL import Image

User = get_user_model()

class ProfileTests(APITestCase):
    def setUp(self):
        self.profile_url = reverse('profile-detail')
        self.kyc_url = reverse('kyc-documents')
        self.basic_kyc_url = reverse('kyc-basic-submit')
        self.email = "profileuser@example.com"
        self.password = "YourSecurePassword123"
        self.user = User.objects.create_user(
            username="profileuser",
            email=self.email,
            password=self.password,
            first_name="Jane",
            last_name="Doe"
        )
        self.client.force_authenticate(user=self.user)

    def get_dummy_image(self):
        file_obj = io.BytesIO()
        image = Image.new('RGB', (100, 100), color=(73, 109, 137))
        image.save(file_obj, 'jpeg')
        file_obj.seek(0)
        return SimpleUploadedFile('test.jpg', file_obj.read(), content_type='image/jpeg')

    def test_retrieve_profile(self):
        """Test retrieving profile."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['user_email'], self.email)

    def test_basic_kyc_submission(self):
        """Test basic KYC questionnaire submission."""
        data = {
            "full_name": "Jane Doe",
            "birth_date": "1990-01-01",
            "nationality": "Nigerian",
            "occupation": "Software Engineer",
            "source_of_funds": "Salary"
        }
        response = self.client.post(self.basic_kyc_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.kyc_level, 'basic')
        self.assertEqual(self.user.profile.kyc_spending_limit_usd, 100)

    def test_kyc_history_creation(self):
        """
        Test that document uploads create new KYCVerification records 
        when all documents are present.
        """
        # Upload all 4 required documents
        data = {
            "identification_document_front": self.get_dummy_image(),
            "identification_document_back": self.get_dummy_image(),
            "selfie": self.get_dummy_image(),
            "proof_of_address": self.get_dummy_image()
        }
        response = self.client.put(self.kyc_url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.user.profile.refresh_from_db()
        self.assertEqual(KYCVerification.objects.filter(profile=self.user.profile).count(), 1)
        
        # Admin rejects
        verification = self.user.profile.latest_verification
        verification.status = 'REJECTED'
        verification.save()
        
        # Re-upload to create new PENDING record
        data_retry = {
            "identification_document_front": self.get_dummy_image(),
            "identification_document_back": self.get_dummy_image(),
            "selfie": self.get_dummy_image(),
            "proof_of_address": self.get_dummy_image()
        }
        self.client.put(self.kyc_url, data_retry, format='multipart')
        self.user.profile.refresh_from_db()
        self.assertEqual(KYCVerification.objects.filter(profile=self.user.profile).count(), 2)
        self.assertEqual(self.user.profile.latest_verification.status, 'PENDING')

    def test_admin_approval_workflow(self):
        """
        Test that admin approval updates profile status and kyc_level.
        """
        # 1. User uploads all documents
        data = {
            "identification_document_front": self.get_dummy_image(),
            "identification_document_back": self.get_dummy_image(),
            "selfie": self.get_dummy_image(),
            "proof_of_address": self.get_dummy_image()
        }
        self.client.put(self.kyc_url, data, format='multipart')
        verification = self.user.profile.latest_verification
        self.assertIsNotNone(verification)
        self.assertEqual(verification.status, 'PENDING')
        
        # 2. Admin approves
        verification.status = 'APPROVED'
        verification.admin_notes = "Everything looks great!"
        verification.save()
        
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.is_complete)
        self.assertEqual(self.user.profile.kyc_level, 'enhanced')
        
        # 3. Verify email
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("APPROVED", mail.outbox[0].subject)

    def test_admin_rejection_workflow(self):
        """
        Test that admin rejection keeps profile incomplete.
        """
        data = {
            "identification_document_front": self.get_dummy_image(),
            "identification_document_back": self.get_dummy_image(),
            "selfie": self.get_dummy_image(),
            "proof_of_address": self.get_dummy_image()
        }
        self.client.put(self.kyc_url, data, format='multipart')
        verification = self.user.profile.latest_verification
        self.assertIsNotNone(verification)
        
        verification.status = 'REJECTED'
        verification.admin_notes = "Selfie is blurry."
        verification.save()
        
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.is_complete)
        self.assertNotEqual(self.user.profile.kyc_level, 'enhanced')
        
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("REJECTED", mail.outbox[0].subject)
