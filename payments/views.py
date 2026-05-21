import uuid
import json
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status, response, views

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import FlutterwaveCustomer, PaymentMethod
from .serializers import (FlutterwaveCustomerSerializer, FlutterwaveCustomerResponseSerializer, CardCreateSerializer,
 PaymentMethodSerializer, PaymentMethodResponseSerializer, PaymentMethodListResponseSerializer, ChargeAuthorizationSerializer)
from .utils import FlutterwaveService
from .webhook_service import FlutterwaveWebhookService
from authentication.permissions import HasPassedKYC

@extend_schema_view(
    retrieve=extend_schema(
        tags=['Payments - Customers'],
        responses={200: FlutterwaveCustomerResponseSerializer}
    ),
    create=extend_schema(
        tags=['Payments - Customers'],
        request=None,
        responses={201: FlutterwaveCustomerResponseSerializer}
    ),
    update=extend_schema(
        tags=['Payments - Customers'],
        responses={200: FlutterwaveCustomerResponseSerializer}
    ),
    partial_update=extend_schema(
        tags=['Payments - Customers'],
        responses={200: FlutterwaveCustomerResponseSerializer}
    ),
    destroy=extend_schema(
        tags=['Payments - Customers'],
        responses={204: None}
    ),
)
class FlutterwaveCustomerViewSet(viewsets.ModelViewSet):
    queryset = FlutterwaveCustomer.objects.all()
    serializer_class = FlutterwaveCustomerSerializer
    permission_classes = [IsAuthenticated, HasPassedKYC]
    lookup_field = 'flutterwave_customer_id'
    http_method_names = ['post', 'get', 'put', 'patch', 'delete']

    def get_queryset(self):
        return FlutterwaveCustomer.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = FlutterwaveCustomerSerializer(instance)
        return response.Response(
            {"message":_("Customer retrieved successfully."), "data": serializer.data},
            status=status.HTTP_200_OK
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        user = request.user
        email = user.email
        first_name = user.first_name
        last_name = user.last_name
        phone_number = getattr(user.profile, 'phone', None) if hasattr(user, 'profile') else None

        if not email:
            return response.Response(
                {"message": _("User email is required to create a Flutterwave customer.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = FlutterwaveService()
        
        # Check if customer already exists in local DB
        if FlutterwaveCustomer.objects.filter(user=user).exists():
            return response.Response(
                {"message": _("Customer already exists for this user.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create in Flutterwave
        fl_response = service.create_customer_object(
            email=email,
            phone_string=phone_number,
            first_name=first_name,
            last_name=last_name
        )

        if fl_response.get('status') == 'success':
            customer_data = fl_response.get('data', {})
            customer = FlutterwaveCustomer.objects.create(
                user=user,
                flutterwave_customer_id=customer_data.get('id'),
                email=customer_data.get('email')
            )
            return response.Response(
                {"message": _("Customer created successfully."), "data": FlutterwaveCustomerSerializer(customer).data},
                status=status.HTTP_201_CREATED
            )
        
        return response.Response(
            {"message": _("Failed to create customer in Flutterwave."), "error": fl_response},
            status=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        
        service = FlutterwaveService()
        fl_response = service.update_customer(
            customer_id=instance.flutterwave_customer_id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone_string=getattr(user.profile, 'phone', None) if hasattr(user, 'profile') else None
        )

        if fl_response.get('status') == 'success':
            # Update local DB if email changed
            if instance.email != user.email:
                instance.email = user.email
                instance.save()
            
            return response.Response(
                {"message": _("Customer updated successfully."), "data": FlutterwaveCustomerSerializer(instance).data},
                status=status.HTTP_200_OK
            )
        
        return response.Response(
            {"message": _("Failed to update customer in Flutterwave."), "error": fl_response},
            status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        service = FlutterwaveService()
        fl_response = service.delete_customer(instance.flutterwave_customer_id)

        if fl_response.get('status') == 'success' or 'not found' in str(fl_response).lower():
            instance.delete()
            return response.Response(
                {"message": _("Customer deleted successfully.")},
                status=status.HTTP_204_NO_CONTENT
            )
        
        return response.Response(
            {"message": _("Failed to delete customer in Flutterwave."), "error": fl_response},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['get'])
    def sync(self, request, flutterwave_customer_id=None):
        """Sync customer data from Flutterwave to local DB."""
        instance = self.get_object()
        service = FlutterwaveService()
        fl_response = service.retrieve_customer(instance.flutterwave_customer_id)

        if fl_response.get('status') == 'success':
            customer_data = fl_response.get('data', {})
            instance.email = customer_data.get('email', instance.email)
            instance.save()
            return response.Response(
                {"message": _("Customer synced successfully."), "data": FlutterwaveCustomerSerializer(instance).data},
                status=status.HTTP_200_OK
            )
        
        return response.Response(
            {"message": _("Failed to sync customer from Flutterwave."), "error": fl_response},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema_view(
    list=extend_schema(
        tags=['Payments - Payment Methods'],
        responses={200: PaymentMethodListResponseSerializer}
    ),
    create=extend_schema(
        tags=['Payments - Payment Methods'],
        request=CardCreateSerializer,
        responses={201: PaymentMethodResponseSerializer}
    ),
    destroy=extend_schema(
        tags=['Payments - Payment Methods'],
        responses={204: None}
    ),
)
class PaymentMethodViewSet(viewsets.GenericViewSet, viewsets.mixins.ListModelMixin, viewsets.mixins.DestroyModelMixin):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated, HasPassedKYC]
    
    def get_queryset(self):
        return PaymentMethod.objects.filter(customer__user=self.request.user)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return response.Response(
            {"message": _("Payment methods retrieved successfully."), "data": serializer.data},
            status=status.HTTP_200_OK
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        user = request.user
        
        try:
            customer = user.flutterwave_customer
        except FlutterwaveCustomer.DoesNotExist:
            return response.Response(
                {"message": _("User does not have a Flutterwave customer object. Please create one first.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CardCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        card_number = serializer.validated_data['card_number']
        cvv = serializer.validated_data['cvv']
        expiry_month = serializer.validated_data['expiry_month']
        expiry_year = serializer.validated_data['expiry_year']
        nonce = serializer.validated_data['nonce']
        
        service = FlutterwaveService()
        idempotency_key = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        
        fl_response = service.create_card_object(
            card_number=card_number,
            cvv=cvv,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            nonce=nonce,
            trace_id=trace_id,
            unique_indempotency_key=idempotency_key
        )
        
        if fl_response.get('status') == 'success':
            data = fl_response.get('data', {})
            pm_id = data.get('id', data.get('token'))
            
            # Extract card metadata from response if available
            card_data = data.get('card', {})
            brand = card_data.get('network') or card_data.get('type')
            last4 = card_data.get('last4')
            exp_month = card_data.get('expiry_month')
            exp_year = card_data.get('expiry_year')

            # If this is the first card, set it as default
            is_default = not PaymentMethod.objects.filter(customer=customer).exists()
            
            payment_method = PaymentMethod.objects.create(
                customer=customer,
                flutterwave_payment_method_id=pm_id,
                nonce=nonce,
                brand=brand,
                last4=last4,
                expiry_month=str(exp_month) if exp_month else None,
                expiry_year=str(exp_year) if exp_year else None,
                idempotency_key=idempotency_key,
                trace_id=trace_id,
                is_active=True,
                is_default=is_default
            )
            
            return response.Response(
                {"message": _("Payment method added successfully."), "data": PaymentMethodSerializer(payment_method).data},
                status=status.HTTP_201_CREATED
            )

            
        return response.Response(
            {"message": _("Failed to add payment method."), "error": fl_response},
            status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        tags=['Payments - Payment Methods'],
        responses={200: PaymentMethodResponseSerializer}
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def set_default(self, request, pk=None):
        instance = self.get_object()
        # Set all other cards for this customer to not default
        PaymentMethod.objects.filter(customer=instance.customer).update(is_default=False)
        # Set this card as default
        instance.is_default = True
        instance.save()
        return response.Response(
            {"message": _("Payment method set as default successfully."), "data": PaymentMethodSerializer(instance).data},
            status=status.HTTP_200_OK
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        customer = instance.customer
        
        # Check if this is the last card and there are active installments
        active_orders = customer.user.orders.filter(status__in=['active', 'pending'])
        has_unpaid_installments = False
        for order in active_orders:
            if order.installments.filter(is_paid=False).exists():
                has_unpaid_installments = True
                break
        
        total_cards = PaymentMethod.objects.filter(customer=customer, is_active=True).count()
        
        if has_unpaid_installments and total_cards <= 1:
            return response.Response(
                {"message": _("Cannot delete the last payment method while you have active installments. Please add a new card first.")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        was_default = instance.is_default
        instance.delete()
        
        # If the deleted card was default, set another one as default if exists
        if was_default:
            next_card = PaymentMethod.objects.filter(customer=customer, is_active=True).first()
            if next_card:
                next_card.is_default = True
                next_card.save()
                
        return response.Response(
            {"message": _("Payment method deleted successfully.")},
            status=status.HTTP_204_NO_CONTENT
        )


    @extend_schema(
        tags=['Payments - Payment Methods'],
        request=ChargeAuthorizationSerializer,
        responses={200: dict}
    )
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def authorize_charge(self, request):
        serializer = ChargeAuthorizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        charge_id = serializer.validated_data['charge_id']
        mode = serializer.validated_data['mode']
        nonce = serializer.validated_data['nonce']
        
        service = FlutterwaveService()
        idempotency_key = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        
        if mode == 'pin':
            encrypted_pin = serializer.validated_data['pin']
            fl_response = service.update_charge_with_pin(
                charge_id, 
                nonce, 
                encrypted_pin,
                trace_id=trace_id
            )
        elif mode == 'otp':
            fl_response = service.update_charge_with_otp(
                charge_id, 
                serializer.validated_data['otp'],
                trace_id=trace_id
            )
            
        if fl_response.get('status') == 'success':
            from django.utils import timezone
            from payments.models import Transaction
            data = fl_response.get('data', {})
            charge_status = data.get('status')
            
            try:
                transaction = Transaction.objects.get(flutterwave_charge_id=str(charge_id))
                transaction.idempotency_key = idempotency_key
                transaction.trace_id = trace_id
                
                is_paid = charge_status and charge_status.lower() in ('successful', 'succeeded')
                
                if is_paid:
                    transaction.status = 'succeeded'
                transaction.save()
                    
                installment = transaction.installments.first()
                if installment:
                    installment.is_paid = True
                    installment.paid_at = timezone.now()
                    installment.save()
                    
                    order = installment.order
                    if order.status == 'pending':
                        order.status = 'active'
                        order.save()
            except Transaction.DoesNotExist:
                pass
                
            return response.Response(
                {"message": _("Charge authorized successfully."), "data": fl_response},
                status=status.HTTP_200_OK
            )
            
        return response.Response(
            {"message": _("Failed to authorize charge."), "error": fl_response},
            status=status.HTTP_400_BAD_REQUEST
        )


@method_decorator(csrf_exempt, name='dispatch')
class FlutterwaveWebhookView(views.APIView):
    """
    Handle incoming Flutterwave webhooks.
    
    Endpoint: POST /api/payments/webhooks/flutterwave/
    
    Flutterwave sends webhook events for:
    - charge.completed: Payment succeeded
    - charge.failed: Payment failed
    - subscription.created: Recurring billing subscription created
    - subscription.cancelled: Recurring billing subscription cancelled
    
    This endpoint:
    1. Validates webhook signature (HMAC-SHA256)
    2. Deduplicates events using event_id
    3. Processes events asynchronously
    4. Returns 200 OK immediately for webhook acknowledgement
    """
    
    permission_classes = []
    
    @extend_schema(
        tags=['Payments - Webhooks'],
        description='Receive Flutterwave webhook events',
        request=None,
        responses={200: dict, 400: dict, 401: dict}
    )
    def post(self, request):
        """
        Receive and process Flutterwave webhook.
        
        Expected headers:
        - X-Flutterwave-Signature: HMAC-SHA256 signature
        
        Returns 200 OK immediately after validating and queuing for processing.
        """
        try:
            # Get raw body for signature verification
            raw_body = request.body
            
            # Verify webhook signature
            if not FlutterwaveWebhookService.verify_webhook_signature(
                request.META,
                raw_body
            ):
                return response.Response(
                    {"message": _("Webhook signature verification failed.")},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Parse JSON payload
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                return response.Response(
                    {"message": _("Invalid JSON payload.")},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process webhook asynchronously or synchronously
            success = FlutterwaveWebhookService.process_webhook(payload)
            
            if not success:
                # Log failure but still return 200 to prevent Flutterwave retries
                pass
            
            # Always return 200 OK to acknowledge receipt
            return response.Response(
                {"message": _("Webhook received and queued for processing.")},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            # Log unexpected errors but still return 200
            return response.Response(
                {"message": _("Webhook received.")},
                status=status.HTTP_200_OK
            )
