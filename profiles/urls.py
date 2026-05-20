from django.urls import path
from .views import ProfileDetailView, KYCDocumentView, KYCVerificationListView, KYCSubmitView, KYCLatestVerificationView, BasicKYCSubmitView

urlpatterns = [
    path('me/', ProfileDetailView.as_view(), name='profile-detail'),
    path('kyc/', KYCDocumentView.as_view(), name='kyc-documents'),
    path('kyc/basic/', BasicKYCSubmitView.as_view(), name='kyc-basic-submit'),
    path('kyc/submit/', KYCSubmitView.as_view(), name='kyc-submit'),
    path('verifications/latest/', KYCLatestVerificationView.as_view(), name='kyc-verification-latest'),
    path('verifications/', KYCVerificationListView.as_view(), name='kyc-verification-list'),
]
