import os
import django
import sys
import phonenumbers
import uuid
import json
import base64
import random
import string
from typing import Dict, Any
from Crypto.Cipher import AES

sys.path.append("/Users/macintoshhd/slash")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import requests
from django.conf import settings


class FlutterwaveService:
    def __init__(self, encrypt_locally: bool = False):
        """
        :param encrypt_locally: If True, the service will encrypt card data and PIN.
                               If False (default), the service expects already-encrypted values
                               (e.g., from a frontend that uses Flutterwave's encryption).
        """
        self.clientId = settings.FLUTTERWAVE_CLIENT_ID
        self.clientSecret = settings.FLUTTERWAVE_CLIENT_SECRET
        self.encryptionKey = settings.FLUTTERWAVE_ENCRYPTION_KEY
        self.base_url = settings.FLUTTERWAVE_BASE_URL
        self.encrypt_locally = encrypt_locally
        self.access_token = self.generate_access_token()

    def generate_access_token(self):
        """
        Step 1: Generate OAuth2 access token.
        Each token is valid for 10 minutes.
        """
        url = "https://idp.flutterwave.com/realms/flutterwave/protocol/openid-connect/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": self.clientId,
            "client_secret": self.clientSecret,
            "grant_type": "client_credentials"
        }
        response = requests.post(url=url, headers=headers, data=data)
        return response.json()["access_token"]

    def parse_phone_number(self, phone_string: str):
        try:
            parsed_number = phonenumbers.parse(phone_string, None)
            if phonenumbers.is_possible_number(parsed_number):
                return {
                    "country_code": parsed_number.country_code,
                    "national_number": parsed_number.national_number,
                    "is_valid": phonenumbers.is_valid_number(parsed_number)
                }
        except phonenumbers.NumberParseException:
            return None

    # Encryption helpers (only used when encrypt_locally=True)
    def encrypt_field(self, plaintext: str, nonce: str) -> str:
        """AES-256-GCM encryption. Nonce must be exactly 12 characters."""
        if len(nonce) != 12:
            raise ValueError("Nonce must be exactly 12 characters")
        key = base64.b64decode(self.encryptionKey)
        iv = nonce.encode('utf-8')
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))
        encrypted = ciphertext + tag
        return base64.b64encode(encrypted).decode('utf-8')

    def generate_nonce(self) -> str:
        """Generate a 12-character alphanumeric nonce."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=12))


    # Customer Management Methods
    def create_customer_object(self, email: str, phone_string: str = None, first_name: str = None,
                               last_name: str = None, trace_id: str = None, access_token: str = None):
        """
        Create a new customer.
        Reference: https://developer.flutterwave.com/reference/customers_create
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        url = f"{self.base_url}/customers"
        if access_token is None:
            access_token = self.generate_access_token()
        bearer = f"Bearer {access_token}"
        headers = {
            "Authorization": bearer,
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        phone_object = self.parse_phone_number(phone_string)
        data = {
            "name": {"first": first_name, "last": last_name},
            "email": email,
            "phone": {
                "country_code": phone_object["country_code"],
                "number": phone_object["national_number"]
            },
        }
        response = requests.post(url=url, headers=headers, data=json.dumps(data))
        return response.json()

    def list_customers(self, page: int = 1, size: int = 10, trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Retrieve a paginated list of all customers.
        
        :param page: The page number to retrieve (default: 1)
        :param size: Number of customers per page (min: 10, max: 50, default: 10)
        :param trace_id: Unique identifier to track this operation (12-255 chars)
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing customers list and pagination info
        
        Reference: https://developer.flutterwave.com/reference/customers_list
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        # Validate parameters per API requirements
        if page < 1:
            page = 1
        if size < 10:
            size = 10
        elif size > 50:
            size = 50
        
        url = f"{self.base_url}/customers"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        params = {
            "page": page,
            "size": size
        }
        
        response = requests.get(url=url, headers=headers, params=params)
        return response.json()

    def retrieve_customer(self, customer_id: str, trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Retrieve a specific customer by ID.
        
        :param customer_id: The ID of the customer to retrieve (e.g., "cus_xxxx")
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing customer details
        
        Reference: https://developer.flutterwave.com/reference/customers_retrieve
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/customers/{customer_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        response = requests.get(url=url, headers=headers)
        return response.json()

    def update_customer(self, customer_id: str, email: str = None, phone_string: str = None,
                        first_name: str = None, last_name: str = None, trace_id: str = None,
                        access_token: str = None) -> Dict[str, Any]:
        """
        Update an existing customer's details.
        
        :param customer_id: The ID of the customer to update
        :param email: Updated email address
        :param phone_string: Updated phone number (with country code)
        :param first_name: Updated first name
        :param last_name: Updated last name
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response with updated customer details
        
        Reference: https://developer.flutterwave.com/reference/customers_update
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/customers/{customer_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        data = {}
        if email:
            data["email"] = email
        if first_name or last_name:
            data["name"] = {}
            if first_name:
                data["name"]["first"] = first_name
            if last_name:
                data["name"]["last"] = last_name
        if phone_string:
            phone_object = self.parse_phone_number(phone_string)
            if phone_object:
                data["phone"] = {
                    "country_code": phone_object["country_code"],
                    "number": phone_object["national_number"]
                }
        
        response = requests.put(url=url, headers=headers, data=json.dumps(data))
        return response.json()

    def search_customers(self, email: str = None, first_name: str = None, last_name: str = None,
                         phone: str = None, trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Search for customers using various criteria.
        
        :param email: Customer's email address
        :param first_name: Customer's first name
        :param last_name: Customer's last name
        :param phone: Customer's phone number
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing matching customers
        
        Reference: https://developer.flutterwave.com/reference/customers_search
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/customers/search"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        params = {}
        if email:
            params["email"] = email
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if phone:
            params["phone"] = phone
        
        response = requests.get(url=url, headers=headers, params=params)
        return response.json()

    def delete_customer(self, customer_id: str, trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Delete a customer by ID.
        
        :param customer_id: The ID of the customer to delete
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response confirming deletion
        
        Reference: https://developer.flutterwave.com/reference/customers_delete
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/customers/{customer_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        response = requests.delete(url=url, headers=headers)
        return response.json()

    # Charge Management Methods
    def list_charges(self, page: int = 1, size: int = 10, status: str = None,
                     from_date: str = None, to_date: str = None,
                     customer_id: str = None, payment_method_id: str = None,
                     trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Retrieve a paginated list of charges with optional filtering.
        
        :param page: The page number to retrieve (default: 1, must be >= 1)
        :param size: Number of charges per page (min: 10, max: 50, default: 10)
        :param status: Filter by charge status (allowed: succeeded, pending, failed, voided)
        :param from_date: Start date/time in ISO 8601 format (e.g., "2024-01-01T00:00:00Z")
        :param to_date: End date/time in ISO 8601 format
        :param customer_id: Filter by customer ID
        :param payment_method_id: Filter by payment method ID
        :param trace_id: Unique identifier to track this operation (12-255 chars)
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing charges list and pagination info
        
        Reference: https://developer.flutterwave.com/reference/charges_list
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        # Validate pagination parameters
        if page < 1:
            page = 1
        if size < 10:
            size = 10
        elif size > 50:
            size = 50
        
        # Validate status if provided
        valid_statuses = ["succeeded", "pending", "failed", "voided"]
        if status and status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        url = f"{self.base_url}/charges"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        params = {
            "page": page,
            "size": size
        }
        
        # Add optional filters
        if status:
            params["status"] = status
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if customer_id:
            params["customer_id"] = customer_id
        if payment_method_id:
            params["payment_method_id"] = payment_method_id
        
        response = requests.get(url=url, headers=headers, params=params)
        return response.json()

    def retrieve_charge(self, charge_id: str, trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Retrieve details of a specific charge by its ID.

        :param charge_id: The ID of the charge to retrieve (e.g., "chg_xxxx")
        :param trace_id: A unique identifier to track this operation (12-255 chars)
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing the charge details

        Reference: https://developer.flutterwave.com/reference/charges_get
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        url = f"{self.base_url}/charges/{charge_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }

        response = requests.get(url=url, headers=headers)
        return response.json()
    
    # Card Payment Methods
    def create_card_object(self, card_number: str, cvv: str, expiry_month: str, expiry_year: str,
                           nonce: str = None, access_token: str = None, trace_id: str = None,
                           unique_indempotency_key: str = None):
        """
        Create a card payment method.
        - If encrypt_locally=True: card_number, cvv, expiry_month, expiry_year must be plaintext;
          they will be encrypted using the generated or provided nonce.
        - If encrypt_locally=False: these fields must already be encrypted (base64 strings);
          nonce must be the same 12-char string used for encryption.
        """
        if self.encrypt_locally:
            # Local encryption mode – generate or use provided nonce
            if nonce is None:
                nonce = self.generate_nonce()
            # Encrypt the plaintext fields
            enc_card = self.encrypt_field(card_number, nonce)
            enc_cvv = self.encrypt_field(cvv, nonce)
            enc_month = self.encrypt_field(expiry_month, nonce)
            enc_year = self.encrypt_field(expiry_year, nonce)
        else:
            # Assume already encrypted; use as‑is
            enc_card = card_number
            enc_cvv = cvv
            enc_month = expiry_month
            enc_year = expiry_year
            if nonce is None:
                raise ValueError("Nonce is required when encrypt_locally=False (must match frontend encryption)")

        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        url = f"{self.base_url}/payment-methods"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id,
            "X-Idempotency-Key": unique_indempotency_key
        }
        data = {
            "type": "card",
            "card": {
                "encrypted_card_number": enc_card,
                "encrypted_cvv": enc_cvv,
                "encrypted_expiry_month": enc_month,
                "encrypted_expiry_year": enc_year,
                "nonce": nonce
            }
        }
        response = requests.post(url=url, headers=headers, data=json.dumps(data))
        return response.json()

    # Charge Methods
    def charge_card_object(self, reference: str, currency: str, customer_id: str,
                           payment_method_id: str, amount: float, redirect_url: str,
                           meta: dict = None, access_token: str = None, trace_id: str = None,
                           idempotency_key: str = None, scenario_key: str = None):
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        if idempotency_key is None:
            idempotency_key = str(uuid.uuid4())

        url = f"{self.base_url}/charges"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id,
            "X-Idempotency-Key": idempotency_key
        }
        if scenario_key:
            headers["X-Scenario-Key"] = scenario_key

        payload = {
            "reference": reference,
            "currency": currency,
            "customer_id": customer_id,
            "payment_method_id": payment_method_id,
            "redirect_url": redirect_url or settings.FLUTTERWAVE_REDIRECT_URL,
            "amount": amount,
            "meta": meta or {}
        }
        response = requests.post(url=url, headers=headers, data=json.dumps(payload))
        print("Response", response.json())
        return response.json()

    def update_charge_with_pin(self, charge_id: str, nonce: str, encrypted_pin: str,
                               access_token: str = None, trace_id: str = None,
                               scenario_key: str = None):
        """
        Update charge with PIN.
        - If encrypt_locally=True: encrypted_pin should be plaintext PIN (will be encrypted).
        - If encrypt_locally=False: encrypted_pin must be already encrypted.
        """
        # The PIN is expected to be already encrypted by the frontend.
        pin_to_send = encrypted_pin

        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        url = f"{self.base_url}/charges/{charge_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        if scenario_key:
            headers["X-Scenario-Key"] = scenario_key

        payload = {
            "authorization": {
                "type": "pin",
                "pin": {
                    "nonce": nonce,
                    "encrypted_pin": pin_to_send
                }
            }
        }
        response = requests.put(url=url, headers=headers, data=json.dumps(payload))
        return response.json()

    def update_charge_with_otp(self, charge_id: str, otp: str,
                               access_token: str = None, trace_id: str = None,
                               scenario_key: str = None):
        """OTP is never encrypted – always plaintext."""
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        url = f"{self.base_url}/charges/{charge_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        if scenario_key:
            headers["X-Scenario-Key"] = scenario_key

        payload = {
            "authorization": {
                "type": "otp",
                "otp": otp
            }
        }
        response = requests.put(url=url, headers=headers, data=json.dumps(payload))
        return response.json()

    def verify_transaction(self, transaction_id: str, access_token: str = None, trace_id: str = None):
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        url = f"{self.base_url}/transactions/{transaction_id}/verify"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        response = requests.get(url=url, headers=headers)
        return response.json()

    def direct_charge(
        self,
        amount: float,
        currency: str,
        reference: str,
        payment_method: dict,
        customer: dict,
        redirect_url: str = None,
        meta: dict = None,
        trace_id: str = None,
        idempotency_key: str = None,
        scenario_key: str = None,
        access_token: str = None,
    ) -> Dict[str, Any]:
        """
        Initiate a direct charge using the Orchestrator endpoint.
        This method creates a charge in a single request, without the need
        to separately create a customer or payment method.

        :param amount: Payment amount (≥ 0.01)[reference:2]
        :param currency: ISO 4217 currency code[reference:3]
        :param reference: Unique transaction reference (6-42 chars)[reference:4]
        :param payment_method: Payment method details (e.g., {"type": "card", "card": {...}})[reference:5]
        :param customer: Customer information (e.g., {"email": "...", "name": {...}, "phone": {...}})[reference:6]
        :param redirect_url: URL to redirect the customer after payment[reference:7]
        :param meta: Additional metadata
        :param trace_id: Unique identifier to track this operation (12-255 chars)[reference:8]
        :param idempotency_key: Unique key to prevent duplicate requests (12-255 chars)[reference:9]
        :param scenario_key: Optional key to simulate specific behaviors or test scenarios[reference:10]
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing charge details and next_action if needed

        Reference: https://developer.flutterwave.com/v4.0/reference/orchestration_direct_charge_post
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        if idempotency_key is None:
            idempotency_key = str(uuid.uuid4())

        url = f"{self.base_url}/orchestration/direct-charges"  # Note: Different endpoint!
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id,
            "X-Idempotency-Key": idempotency_key,
        }
        if scenario_key:
            headers["X-Scenario-Key"] = scenario_key

        payload = {
            "amount": amount,
            "currency": currency,
            "reference": reference,
            "payment_method": payment_method,
            "customer": customer,
        }
        if redirect_url:
            payload["redirect_url"] = redirect_url
        if meta:
            payload["meta"] = meta

        response = requests.post(url=url, headers=headers, data=json.dumps(payload))
        return response.json()

    # Payment Plans Management (for Recurring Billing)
    def create_payment_plan(self, name: str, interval: str, amount: float = None,
                            currency: str = "NGN", duration: int = None,
                            trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Create a payment plan that defines the billing schedule for subscriptions.
        
        :param name: The name of the plan (used in email reminders)
        :param interval: Billing interval (e.g., daily, weekly, monthly, yearly, 
                        or custom like "every five months")
        :param amount: Amount to charge each time (optional, can be set when charging)
        :param currency: Currency to charge in (default: NGN)
        :param duration: How long the subscription lasts (in terms of intervals).
                        If not specified, charges continue indefinitely.
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing the created payment plan
        
        Reference: https://developer.flutterwave.com/v3.0/reference/create-payment-plan-1
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/payment-plans"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        payload = {
            "name": name,
            "interval": interval,
            "currency": currency
        }
        if amount is not None:
            payload["amount"] = amount
        if duration is not None:
            payload["duration"] = duration
        
        response = requests.post(url=url, headers=headers, data=json.dumps(payload))
        return response.json()

    def list_payment_plans(self, page: int = 1, size: int = 10,
                        trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Retrieve a paginated list of all payment plans.
        
        :param page: Page number to retrieve (default: 1)
        :param size: Number of plans per page (min: 10, max: 50, default: 10)
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing payment plans list and pagination info
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        if page < 1:
            page = 1
        if size < 10:
            size = 10
        elif size > 50:
            size = 50
        
        url = f"{self.base_url}/payment-plans"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        params = {"page": page, "size": size}
        
        response = requests.get(url=url, headers=headers, params=params)
        return response.json()

    def get_payment_plan(self, plan_id: str, trace_id: str = None,
                        access_token: str = None) -> Dict[str, Any]:
        """
        Retrieve a specific payment plan by ID.
        
        :param plan_id: The ID of the payment plan to retrieve
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing the payment plan details
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/payment-plans/{plan_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        response = requests.get(url=url, headers=headers)
        return response.json()

    def cancel_payment_plan(self, plan_id: str, trace_id: str = None,
                            access_token: str = None) -> Dict[str, Any]:
        """
        Cancel a payment plan. This will also cancel all associated subscriptions.
        
        :param plan_id: The ID of the payment plan to cancel
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response confirming cancellation
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/payment-plans/{plan_id}/cancel"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        response = requests.put(url=url, headers=headers)
        return response.json()

    # Subscription Management (for Recurring Payments)
    def create_subscription(self, customer_id: str, payment_method_id: str, plan_id: str,
                            amount: float = None, start_date: str = None,
                            trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Create a subscription by charging the customer and subscribing them to a payment plan.
        
        :param customer_id: The ID of the customer
        :param payment_method_id: The ID of the saved payment method (card)
        :param plan_id: The ID of the payment plan to subscribe to
        :param amount: Optional amount (overrides the plan's default amount)
        :param start_date: Optional start date in ISO 8601 format (e.g., "2024-12-01T00:00:00Z")
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing the subscription details
        
        Note: After the first successful charge, the customer is automatically subscribed
        to the plan. Flutterwave will handle subsequent billing cycles automatically.
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        # First, charge the customer to initiate the subscription
        url = f"{self.base_url}/subscriptions"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        payload = {
            "customer_id": customer_id,
            "payment_method_id": payment_method_id,
            "plan_id": plan_id
        }
        if amount is not None:
            payload["amount"] = amount
        if start_date is not None:
            payload["start_date"] = start_date
        
        response = requests.post(url=url, headers=headers, data=json.dumps(payload))
        return response.json()

    def list_subscriptions(self, email: str = None, status: str = None,
                        page: int = 1, trace_id: str = None,
                        access_token: str = None) -> Dict[str, Any]:
        """
        Retrieve a list of all subscriptions, with optional filtering.
        
        :param email: Filter by customer email
        :param status: Filter by subscription status (active or cancelled)
        :param page: Page number to retrieve (default: 1)
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing subscriptions list and pagination info
        
        Reference: https://developer.flutterwave.com/v3.0.0/reference/get-all-subscriptions
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/subscriptions"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        params = {"page": page}
        if email:
            params["email"] = email
        if status:
            if status not in ["active", "cancelled"]:
                raise ValueError("Status must be either 'active' or 'cancelled'")
            params["status"] = status
        
        response = requests.get(url=url, headers=headers, params=params)
        return response.json()

    def get_subscription(self, subscription_id: str, trace_id: str = None,
                        access_token: str = None) -> Dict[str, Any]:
        """
        Retrieve details of a specific subscription by ID.
        
        :param subscription_id: The ID of the subscription to retrieve
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing the subscription details
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/subscriptions/{subscription_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        response = requests.get(url=url, headers=headers)
        return response.json()

    def cancel_subscription(self, subscription_id: str, trace_id: str = None,
                            access_token: str = None) -> Dict[str, Any]:
        """
        Cancel an active subscription.
        
        :param subscription_id: The ID of the subscription to cancel
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response confirming cancellation
        
        Reference: https://developer.flutterwave.com/v3.0/reference/cancel-a-subscription-1
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/subscriptions/{subscription_id}/cancel"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        response = requests.put(url=url, headers=headers)
        return response.json()

    # Tokenized Charges (Card on File for Recurring Payments)
    def tokenized_charge(self, token: str, amount: float, currency: str, email: str,
                        country: str = None, preauthorize: bool = False,
                        trace_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Process a tokenized charge using a previously saved card token.
        This is used for recurring payments after the initial customer consent.
        
        :param token: The card token (e.g., "flw-t1nf-1dd5c21361bb85c64deb7ff57ec891b2-m03k")
        :param amount: Amount to charge
        :param currency: Currency code (e.g., "NGN", "USD")
        :param email: Customer's email address
        :param country: Country code (e.g., "NG")
        :param preauthorize: Set to True for preauthorized charges
        :param trace_id: Unique identifier to track this operation
        :param access_token: Optional access token (generated if not provided)
        :return: API response containing the charge result
        
        Reference: https://developer.flutterwave.com/docs/card-on-file
        """
        if access_token is None:
            access_token = self.generate_access_token()
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        url = f"{self.base_url}/tokenized-charges"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        payload = {
            "token": token,
            "amount": amount,
            "currency": currency,
            "email": email,
            "preauthorize": preauthorize
        }
        if country:
            payload["country"] = country
        
        response = requests.post(url=url, headers=headers, data=json.dumps(payload))
        return response.json()