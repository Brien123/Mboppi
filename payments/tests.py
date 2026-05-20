from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from django.core import mail
from django.utils import timezone
from orders.models import Order, PaymentInstallment
from payments.models import FlutterwaveCustomer, PaymentMethod
from payments.tasks import process_scheduled_payments

class PaymentNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.order = Order.objects.create(
            user=self.user,
            total_base_price=100.00,
            total_local_price=100000.00,
            currency_code='NGN',
            payment_plan='4W',
            status='active'
        )
        
        # Clear signal-created installments to have full control in tests
        self.order.installments.all().delete()
        
        self.installment = PaymentInstallment.objects.create(
            order=self.order,
            due_date=timezone.now().date(),
            amount_base=25.00,
            amount_local=25000.00,
            is_paid=False
        )

    @patch('payments.tasks.FlutterwaveService')
    def test_payment_failure_sends_email(self, mock_service_class):
        # Setup mock customer and payment method
        customer = FlutterwaveCustomer.objects.create(
            user=self.user,
            flutterwave_customer_id='flw-cust-123'
        )
        PaymentMethod.objects.create(
            customer=customer,
            flutterwave_payment_method_id='flw-pm-123',
            is_active=True,
            is_default=True
        )
        
        # Mock Flutterwave failure response
        mock_service = mock_service_class.return_value
        mock_service.charge_card_object.return_value = {
            'status': 'error',
            'message': 'Insufficient funds',
            'data': {}
        }
        
        # Run the task
        process_scheduled_payments()
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn('Payment Failed', mail.outbox[0].subject)
        self.assertIn('Insufficient funds', mail.outbox[0].body)
        self.assertIn(self.order.order_id.hex[:10].upper(), mail.outbox[0].body)

    @patch('payments.tasks.FlutterwaveService')
    def test_no_payment_method_sends_email(self, mock_service_class):
        # Create customer but no payment method
        FlutterwaveCustomer.objects.create(
            user=self.user,
            flutterwave_customer_id='flw-cust-123'
        )
        
        # Run the task
        process_scheduled_payments()
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('No active payment method on file', mail.outbox[0].body)

    @patch('payments.tasks.FlutterwaveService')
    def test_no_customer_sends_email(self, mock_service_class):
        # User has no FlutterwaveCustomer
        
        # Run the task
        process_scheduled_payments()
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('No registered payment profile found', mail.outbox[0].body)

    @patch('payments.tasks.FlutterwaveService')
    def test_successful_charge_no_email(self, mock_service_class):
        # Setup mock customer and payment method
        customer = FlutterwaveCustomer.objects.create(
            user=self.user,
            flutterwave_customer_id='flw-cust-123'
        )
        PaymentMethod.objects.create(
            customer=customer,
            flutterwave_payment_method_id='flw-pm-123',
            is_active=True,
            is_default=True
        )
        
        # Mock Flutterwave success response
        mock_service = mock_service_class.return_value
        mock_service.charge_card_object.return_value = {
            'status': 'success',
            'data': {
                'id': 12345,
                'status': 'successful',
                'amount': 25000,
                'currency': 'NGN'
            }
        }
        
        # Run the task
        process_scheduled_payments()
        
        # Verify NO failure email was sent
        self.assertEqual(len(mail.outbox), 0)
        
        # Verify installment marked as paid
        self.installment.refresh_from_db()
        self.assertTrue(self.installment.is_paid)
