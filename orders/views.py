import uuid
from django.conf import settings
from django.db import transaction
from rest_framework import viewsets, status

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes
from django.utils import timezone
from payments.models import FlutterwaveCustomer, Transaction
from payments.serializers import TransactionSerializer, TransactionListResponseSerializer
from .models import Order
from .serializers import (
    OrderSerializer, CheckoutSerializer,
    OrderResponseSerializer, OrderListResponseSerializer
)
from payments.utils import FlutterwaveService
from authentication.permissions import HasPassedKYC


@extend_schema_view(
    list=extend_schema(
        tags=['Orders'],
        responses={200: OrderListResponseSerializer}
    ),
    retrieve=extend_schema(
        tags=['Orders'],
        responses={200: OrderResponseSerializer},
        parameters=[
            OpenApiParameter(name='order_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH)
        ]
    ),
    create=extend_schema(
        tags=['Orders'],
        request=OrderSerializer,
        responses={201: OrderResponseSerializer}
    ),
    update=extend_schema(
        tags=['Orders'],
        request=OrderSerializer,
        responses={200: OrderResponseSerializer},
        parameters=[
            OpenApiParameter(name='order_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH)
        ]
    ),
    partial_update=extend_schema(
        tags=['Orders'],
        request=OrderSerializer,
        responses={200: OrderResponseSerializer},
        parameters=[
            OpenApiParameter(name='order_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH)
        ]
    ),
    destroy=extend_schema(
        tags=['Orders'],
        responses={204: None},
        parameters=[
            OpenApiParameter(name='order_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH)
        ]
    ),
)
class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasPassedKYC]
    serializer_class = OrderSerializer
    lookup_field = 'order_id'

    def get_queryset(self):
        if getattr(self, "privileged_queryset", False) or not self.request:
            return Order.objects.all().prefetch_related('items', 'installments')
        return Order.objects.filter(user=self.request.user).prefetch_related('items', 'installments')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data)
            return Response(
                {"message": _("Orders retrieved successfully."), "data": response_data.data},
                status=status.HTTP_200_OK
            )
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {"message": _("Orders retrieved successfully."), "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(
            {"message": _("Order retrieved successfully."), "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {"message": _("Order created successfully."), "data": serializer.data},
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(
            {"message": _("Order updated successfully."), "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"message": _("Order deleted successfully."), "data": None},
            status=status.HTTP_204_NO_CONTENT
        )

    @extend_schema(
        summary="Create a new order with payment plan",
        description="Place an order with selected products and a payment plan. Installments are generated automatically.",
        tags=['Orders'],
        request=CheckoutSerializer,
        responses={201: OrderResponseSerializer}
    )
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def checkout(self, request):
        user = request.user

        has_card = False
        if hasattr(user, 'flutterwave_customer'):
            has_card = user.flutterwave_customer.payment_methods.filter(is_active=True).exists()

        if not has_card:
            return Response(
                {"message": _("Please add a payment card before checking out.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        first_installment = order.installments.order_by('due_date').first()
        customer = user.flutterwave_customer
        payment_method = customer.payment_methods.filter(is_active=True, is_default=True).first() or customer.payment_methods.filter(is_active=True).first()


        payment_action = None

        if first_installment and payment_method:
            service = FlutterwaveService()
            reference = f"charge{order.order_id.hex[:10]}{first_installment.id}"
            redirect_url = settings.FLUTTERWAVE_REDIRECT_URL
            
            idempotency_key = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())

            fl_response = service.charge_card_object(
                reference=reference,
                currency=order.currency_code,
                customer_id=user.flutterwave_customer.flutterwave_customer_id,
                payment_method_id=payment_method.flutterwave_payment_method_id,
                amount=float(first_installment.amount_local),
                redirect_url=redirect_url,
                idempotency_key=idempotency_key,
                trace_id=trace_id
            )

            status_str = fl_response.get('status')
            data = fl_response.get('data', {})

            if status_str == 'success':
                charge_status = data.get('status')
                # Determine if payment succeeded (both 'successful' and 'succeeded' are accepted)
                is_paid = charge_status and charge_status.lower() in ('successful', 'succeeded')

                # Create transaction with correct status
                transaction = Transaction.objects.create(
                    customer=user.flutterwave_customer,
                    payment_method=payment_method,
                    flutterwave_charge_id=str(data.get('id', '')),
                    reference=reference,
                    amount=first_installment.amount_local,
                    currency=order.currency_code,
                    status='succeeded' if is_paid else 'pending',
                    idempotency_key=idempotency_key,
                    trace_id=trace_id,
                    order=order
                )

                first_installment.transaction = transaction
                if is_paid:
                    first_installment.is_paid = True
                    first_installment.paid_at = timezone.now()
                    order.status = 'active'
                    order.save()
                first_installment.save()

                auth_mode = data.get('meta', {}).get('authorization', {}).get('mode')
                if auth_mode:
                    payment_action = fl_response
            else:
                return Response(
                    {"message": _("Order placed but down payment failed."), "error": fl_response},
                    status=status.HTTP_400_BAD_REQUEST
                )

        response_data = {
            "message": _("Order placed successfully."),
            "data": OrderSerializer(order).data
        }
        if payment_action:
            response_data["payment_action"] = payment_action

        return Response(response_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Pay off the remaining balance",
        description="Pay all remaining unpaid installments for an order at once using the saved payment method.",
        tags=['Orders'],
        request=None,
        responses={200: OrderResponseSerializer},
        parameters=[
            OpenApiParameter(name='order_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH)
        ]

    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def payoff(self, request, order_id=None):
        order = self.get_object()
        user = request.user
        
        # Find unpaid installments
        unpaid_installments = order.installments.filter(is_paid=False)
        if not unpaid_installments.exists():
            return Response(
                {"message": _("This order is already fully paid.")}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate remaining balance
        total_remaining = sum(inst.amount_local for inst in unpaid_installments)
        
        # Get saved payment method
        try:
            customer = user.flutterwave_customer
            payment_method = customer.payment_methods.filter(is_active=True, is_default=True).first() or customer.payment_methods.filter(is_active=True).first()

        except FlutterwaveCustomer.DoesNotExist:
            return Response(
                {"message": _("User has no Flutterwave customer profile.")}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if not payment_method:
            return Response(
                {"message": _("No active payment method found. Please add a card first.")}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        service = FlutterwaveService()
        reference = f"payoff_{order.order_id.hex[:10]}_{uuid.uuid4().hex[:6]}"
        idempotency_key = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        
        fl_response = service.charge_card_object(
            reference=reference,
            currency=order.currency_code,
            customer_id=customer.flutterwave_customer_id,
            payment_method_id=payment_method.flutterwave_payment_method_id,
            amount=float(total_remaining),
            redirect_url=settings.FLUTTERWAVE_REDIRECT_URL,
            idempotency_key=idempotency_key,
            trace_id=trace_id
        )
        
        if fl_response.get('status') == 'success':
            data = fl_response.get('data', {})
            charge_status = data.get('status')
            is_paid = charge_status and charge_status.lower() in ('successful', 'succeeded')
            
            transaction = Transaction.objects.create(
                customer=customer,
                payment_method=payment_method,
                flutterwave_charge_id=str(data.get('id', '')),
                reference=reference,
                amount=total_remaining,
                currency=order.currency_code,
                status='succeeded' if is_paid else 'pending',
                idempotency_key=idempotency_key,
                trace_id=trace_id,
                order=order
            )
            
            if is_paid:
                for inst in unpaid_installments:
                    inst.is_paid = True
                    inst.paid_at = timezone.now()
                    inst.transaction = transaction
                    inst.save()
                
                order.status = 'completed'
                order.save()
                
                return Response({
                    "message": _("Remaining balance paid successfully."), 
                    "data": OrderSerializer(order).data
                })
            
            return Response({
                "message": _("Payment initiated but requires further authorization."), 
                "data": fl_response
            })
            
        return Response(
            {"message": _("Payment failed."), "error": fl_response}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        summary="View payment history for an order",
        description="Returns every successful and failed payment attempt (transaction) for a specific order.",
        tags=['Orders'],
        responses={200: TransactionListResponseSerializer},
        parameters=[
            OpenApiParameter(name='order_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH)
        ]
    )
    @action(detail=True, methods=['get'], url_path='payment-history')
    def payment_history(self, request, order_id=None):
        order = self.get_object()
        
        # Get all transactions associated with this order
        transactions = Transaction.objects.filter(
            order=order,
            customer__user=request.user
        ).order_by('-created_at')
        
        serializer = TransactionSerializer(transactions, many=True)
        
        return Response(
            {
                "message": _("Payment history retrieved successfully."),
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )