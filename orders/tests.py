from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from products.models import Category, Product
from cart.models import Cart, CartItem
from payments.models import FlutterwaveCustomer, PaymentMethod
from payments.utils import FlutterwaveService
import uuid

User = get_user_model()

from django.test import override_settings

@override_settings(FLUTTERWAVE_REDIRECT_URL='https://example.com/payment-callback')
class CheckoutIntegrationTest(APITestCase):

    def setUp(self):
        self.email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        self.user = User.objects.create_user(
            username=f"user_{uuid.uuid4().hex[:8]}",
            email=self.email,
            password="testpassword123",
            first_name="Chidi",
            last_name="Okonkwo"
        )
        
        # Create profile and KYC verification
        from profiles.models import Profile, KYCVerification
        self.profile = self.user.profile
        self.profile.is_complete = True
        self.profile.save()
        self.kyc = KYCVerification.objects.create(profile=self.profile, status='APPROVED')

        # Auth user
        self.client.force_authenticate(user=self.user)

        # Create category and product
        self.category = Category.objects.create(name="Electronics", slug="electronics")
        self.product = Product.objects.create(
            category=self.category,
            name="Test Smartphone",
            slug="test-smartphone",
            base_price=5000.00,
            stock=10
        )

        # Create cart and add product
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=1
        )

        # Initialize Flutterwave Service
        self.fw = FlutterwaveService()
        self.customer_id = None

    def tearDown(self):
        # Delete customer from flutterwave to cleanup
        if self.customer_id:
            try:
                self.fw.delete_customer(self.customer_id)
            except Exception as e:
                print(f"Cleanup error: {e}")

    def test_checkout_with_card(self):
        # 1. Create Flutterwave Customer
        print("\n" + "="*60)
        print("STEP 1: Creating Customer (Nigerian details)")
        print("="*60)
        customer_response = self.fw.create_customer_object(
            email=self.user.email,
            phone_string="+2348102447007",
            first_name=self.user.first_name,
            last_name=self.user.last_name
        )
        if customer_response.get('status') == 'failed' and customer_response.get('error', {}).get('type') == 'RESOURCE_CONFLICT':
            print("ℹ️ Customer already exists, retrieving existing...")
            search_response = self.fw.search_customers(email=self.user.email)
            print(f"Search Response: {search_response}")
            if search_response.get('status') == 'success' and search_response.get('data'):
                self.customer_id = search_response["data"][0]["id"]
            else:
                # Fallback: maybe just use the email if we can't get ID? 
                # Or try to get it from the conflict error message if possible (usually not).
                # Let's assume we can find it.
                raise Exception(f"Could not retrieve existing customer: {search_response}")
        else:
            self.assertEqual(customer_response.get('status'), 'success', f"Customer creation failed: {customer_response}")
            self.customer_id = customer_response["data"]["id"]
        print(f"✅ Customer ID: {self.customer_id}")

        # Save to local DB
        fw_customer = FlutterwaveCustomer.objects.create(
            user=self.user,
            flutterwave_customer_id=self.customer_id,
            email=self.user.email
        )

        # 2. Create Card Payment Method
        print("\n" + "="*60)
        print("STEP 2: Creating Card Payment Method")
        print("="*60)
        test_card_number = "5111111111111118"
        test_cvv = "123"
        test_expiry_month = "12"
        test_expiry_year = "30"

        nonce = self.fw.generate_nonce()
        encrypted_card = self.fw.encrypt_field(test_card_number, nonce)
        encrypted_cvv = self.fw.encrypt_field(test_cvv, nonce)
        encrypted_month = self.fw.encrypt_field(test_expiry_month, nonce)
        encrypted_year = self.fw.encrypt_field(test_expiry_year, nonce)

        card_response = self.fw.create_card_object(
            card_number=encrypted_card,
            cvv=encrypted_cvv,
            expiry_month=encrypted_month,
            expiry_year=encrypted_year,
            nonce=nonce,
            unique_indempotency_key=str(uuid.uuid4())
        )
        self.assertEqual(card_response.get('status'), 'success', f"Card creation failed: {card_response}")
        
        payment_method_id = card_response["data"]["id"]
        print(f"✅ Payment Method ID: {payment_method_id}")

        # Save to local DB
        PaymentMethod.objects.create(
            customer=fw_customer,
            flutterwave_payment_method_id=payment_method_id,
            nonce=nonce,
            is_active=True
        )

        # 3. Perform Checkout
        print("\n" + "="*60)
        print("STEP 3: Performing Checkout")
        print("="*60)
        url = reverse('orders-checkout')
        data = {
            "items": [
                {
                    "product_id": self.product.id,
                    "quantity": 1
                }
            ],
            "payment_plan": "4W",
            "delivery_details": {
                "full_name": "Chidi Okonkwo",
                "phone_number": "+2348102447007",
                "address": "123 Test Street",
                "city": "Lagos",
                "state": "Lagos",
                "postal_code": "100001"
            }
        }
        
        response = self.client.post(url, data, format='json')
        print(response.data)
        
        # 4. Assertions
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("data", response.data)
        self.assertIn("delivery_detail", response.data["data"])
        self.assertEqual(response.data["data"]["delivery_detail"]["full_name"], "Chidi Okonkwo")
        
        # Verify transaction fields
        from payments.models import Transaction
        transaction = Transaction.objects.get(order__order_id=response.data['data']['order_id'])
        self.assertIsNotNone(transaction.idempotency_key)
        self.assertIsNotNone(transaction.trace_id)
        print(f"✅ Transaction Key: {transaction.idempotency_key}")
        print(f"✅ Transaction Trace: {transaction.trace_id}")
        
        print("\n" + "="*60)
        print("TEST COMPLETED")
        print("="*60)
