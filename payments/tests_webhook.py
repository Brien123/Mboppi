import json
import hmac
import hashlib
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from .models import (
    FlutterwaveCustomer, PaymentMethod, Transaction, WebhookEvent
)
from .webhook_service import FlutterwaveWebhookService
from orders.models import Order


User = get_user_model()


class FlutterwaveWebhookServiceTestCase(TestCase):
    """Test webhook service signature verification and event processing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test11144100@exampless.com',
            password='testpass123'
        )
        self.customer = FlutterwaveCustomer.objects.create(
            user=self.user,
            flutterwave_customer_id='cus_test_123',
            email='test11144100@exampless.com'
        )
        self.payment_method = PaymentMethod.objects.create(
            customer=self.customer,
            flutterwave_payment_method_id='pmd_test_123',
            nonce='test_nonce_12',
            is_default=True
        )
        self.order = Order.objects.create(
            user=self.user,
            currency_code='NGN',
            status='pending',
            total_base_price=10000.00,
            total_local_price=10000.00,
            payment_plan='FP'
        )
        self.transaction = Transaction.objects.create(
            customer=self.customer,
            payment_method=self.payment_method,
            flutterwave_charge_id='chg_test_123',
            reference='test_ref_123',
            amount=10000.00,
            currency='NGN',
            status='pending',
            order=self.order
        )

    @override_settings(FLUTTERWAVE_WEBHOOK_SECRET='test_secret_key')
    def test_verify_webhook_signature_valid(self):
        """Test valid webhook signature verification."""
        secret = 'test_secret_key'
        body = b'{"test": "payload"}'
        
        signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Flutterwave-Signature': signature}
        result = FlutterwaveWebhookService.verify_webhook_signature(headers, body)
        self.assertTrue(result)

    @override_settings(FLUTTERWAVE_WEBHOOK_SECRET='test_secret_key')
    def test_verify_webhook_signature_invalid(self):
        """Test invalid webhook signature verification."""
        body = b'{"test": "payload"}'
        headers = {'X-Flutterwave-Signature': 'invalid_signature'}
        
        result = FlutterwaveWebhookService.verify_webhook_signature(headers, body)
        self.assertFalse(result)

    @override_settings(FLUTTERWAVE_WEBHOOK_SECRET='test_secret_key')
    def test_verify_webhook_signature_missing_header(self):
        """Test webhook verification with missing signature header."""
        body = b'{"test": "payload"}'
        headers = {}
        
        result = FlutterwaveWebhookService.verify_webhook_signature(headers, body)
        self.assertFalse(result)

    def test_process_webhook_charge_completed(self):
        """Test processing charge.completed event."""
        payload = {
            'webhook_id': 'wbk_test_123',
            'type': 'charge.completed',
            'data': {
                'id': 'chg_test_123',
                'reference': 'test_ref_123',
                'status': 'succeeded',
                'amount': 10000,
                'currency': 'NGN'
            }
        }
        
        result = FlutterwaveWebhookService.process_webhook(payload)
        self.assertTrue(result)
        
        # Verify transaction status updated
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'succeeded')
        
        # Verify WebhookEvent created and processed
        webhook_event = WebhookEvent.objects.get(event_id='wbk_test_123')
        self.assertEqual(webhook_event.status, 'processed')
        self.assertEqual(webhook_event.event_type, 'charge.completed')

    def test_process_webhook_charge_failed(self):
        """Test processing charge.failed event."""
        payload = {
            'webhook_id': 'wbk_failed_123',
            'type': 'charge.failed',
            'data': {
                'id': 'chg_test_123',
                'reference': 'test_ref_123',
                'status': 'failed'
            }
        }
        
        result = FlutterwaveWebhookService.process_webhook(payload)
        self.assertTrue(result)
        
        # Verify transaction status updated to failed
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'failed')

    def test_process_webhook_idempotency(self):
        """Test webhook idempotency - duplicate events are not reprocessed."""
        payload = {
            'webhook_id': 'wbk_dup_123',
            'type': 'charge.completed',
            'data': {
                'id': 'chg_test_123',
                'reference': 'test_ref_123',
                'status': 'succeeded'
            }
        }
        
        # Process same event twice
        result1 = FlutterwaveWebhookService.process_webhook(payload)
        self.assertTrue(result1)
        
        # Update transaction to verify it was processed
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'succeeded')
        
        # Mark transaction as pending again to verify it's not reprocessed
        self.transaction.status = 'pending'
        self.transaction.save()
        
        # Process same event again
        result2 = FlutterwaveWebhookService.process_webhook(payload)
        self.assertTrue(result2)
        
        # Verify transaction status stayed pending (not reprocessed)
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'pending')

    def test_process_webhook_missing_event_id(self):
        """Test webhook processing with missing webhook_id."""
        payload = {
            'type': 'charge.completed',
            'data': {'id': 'chg_test_123'}
        }
        
        result = FlutterwaveWebhookService.process_webhook(payload)
        self.assertFalse(result)

    def test_process_webhook_unknown_event_type(self):
        """Test webhook processing with unknown event type."""
        payload = {
            'webhook_id': 'wbk_unknown_123',
            'type': 'unknown.event',
            'data': {}
        }
        
        result = FlutterwaveWebhookService.process_webhook(payload)
        self.assertTrue(result)
        
        # Verify event marked as ignored
        webhook_event = WebhookEvent.objects.get(event_id='wbk_unknown_123')
        self.assertEqual(webhook_event.status, 'ignored')


class FlutterwaveWebhookEndpointTestCase(TestCase):
    """Test webhook HTTP endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.webhook_url = '/api/payments/webhooks/flutterwave/'
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test11144100@exampless.com',
            password='testpass123'
        )
        self.customer = FlutterwaveCustomer.objects.create(
            user=self.user,
            flutterwave_customer_id='cus_test_123',
            email='test11144100@exampless.com'
        )
        self.payment_method = PaymentMethod.objects.create(
            customer=self.customer,
            flutterwave_payment_method_id='pmd_test_123',
            nonce='test_nonce_12'
        )
        self.order = Order.objects.create(
            user=self.user,
            currency_code='NGN',
            status='pending',
            total_base_price=10000.00,
            total_local_price=10000.00,
            payment_plan='FP'
        )
        self.transaction = Transaction.objects.create(
            customer=self.customer,
            payment_method=self.payment_method,
            flutterwave_charge_id='chg_test_123',
            reference='test_ref_123',
            amount=10000.00,
            currency='NGN',
            status='pending',
            order=self.order
        )

    @override_settings(FLUTTERWAVE_WEBHOOK_SECRET='test_secret_key')
    def test_webhook_endpoint_valid_signature(self):
        """Test webhook endpoint with valid signature."""
        payload = {
            'webhook_id': 'wbk_test_456',
            'type': 'charge.completed',
            'data': {
                'id': 'chg_test_123',
                'reference': 'test_ref_123',
                'status': 'succeeded'
            }
        }
        
        body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(
            'test_secret_key'.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        response = self.client.post(
            self.webhook_url,
            data=body,
            content_type='application/json',
            HTTP_X_FLUTTERWAVE_SIGNATURE=signature
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('received', response.json()['message'].lower())

    @override_settings(FLUTTERWAVE_WEBHOOK_SECRET='test_secret_key')
    def test_webhook_endpoint_invalid_signature(self):
        """Test webhook endpoint with invalid signature."""
        payload = {
            'webhook_id': 'wbk_test_789',
            'type': 'charge.completed',
            'data': {'id': 'chg_test_123'}
        }
        
        body = json.dumps(payload).encode('utf-8')
        
        response = self.client.post(
            self.webhook_url,
            data=body,
            content_type='application/json',
            HTTP_X_FLUTTERWAVE_SIGNATURE='invalid_signature'
        )
        
        self.assertEqual(response.status_code, 401)

    @override_settings(FLUTTERWAVE_WEBHOOK_SECRET='')
    def test_webhook_endpoint_no_secret_configured(self):
        """Test webhook endpoint when no secret is configured (skips verification)."""
        payload = {
            'webhook_id': 'wbk_test_no_secret',
            'type': 'charge.completed',
            'data': {
                'id': 'chg_test_123',
                'reference': 'test_ref_123',
                'status': 'succeeded'
            }
        }
        
        body = json.dumps(payload).encode('utf-8')
        
        response = self.client.post(
            self.webhook_url,
            data=body,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)

    def test_webhook_endpoint_invalid_json(self):
        """Test webhook endpoint with invalid JSON."""
        response = self.client.post(
            self.webhook_url,
            data=b'invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)

    @override_settings(FLUTTERWAVE_WEBHOOK_SECRET='')
    def test_webhook_endpoint_csrf_exempt(self):
        """Test that webhook endpoint is CSRF exempt."""
        payload = {
            'webhook_id': 'wbk_csrf_test',
            'type': 'charge.completed',
            'data': {'id': 'chg_test_123'}
        }
        
        body = json.dumps(payload).encode('utf-8')
        
        # Should work without CSRF token
        response = self.client.post(
            self.webhook_url,
            data=body,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
