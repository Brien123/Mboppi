from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FlutterwaveCustomerViewSet, PaymentMethodViewSet, FlutterwaveWebhookView

router = DefaultRouter()
router.register(r'customers', FlutterwaveCustomerViewSet, basename='customer')
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-method')

urlpatterns = [
    path('', include(router.urls)),
    path('webhooks/flutterwave/', FlutterwaveWebhookView.as_view(), name='flutterwave-webhook'),
]
