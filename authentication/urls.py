from django.urls import path
from .views import (
    RegisterView, OTPSendView, OTPVerifyView, LoginView,
    RefreshTokenView, LogoutView,
    ChangeEmailRequestView, ChangeEmailConfirmView,
    ChangePasswordView,
    ForgotPasswordRequestView, ForgotPasswordResetView,
    GoogleSocialAuthView, DeactivateAccountView
)

urlpatterns = [
    # Registration & OTP
    path('signup/', RegisterView.as_view(), name='signup'),
    path('otp/send/', OTPSendView.as_view(), name='otp-send'),
    path('otp/verify/', OTPVerifyView.as_view(), name='otp-verify'),

    # Session
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # Account management (authenticated)
    path('email/change/', ChangeEmailRequestView.as_view(), name='email-change-request'),
    path('email/change/confirm/', ChangeEmailConfirmView.as_view(), name='email-change-confirm'),
    path('password/change/', ChangePasswordView.as_view(), name='password-change'),

    # Forgot password (public)
    path('password/forgot/', ForgotPasswordRequestView.as_view(), name='password-forgot-request'),
    path('password/forgot/reset/', ForgotPasswordResetView.as_view(), name='password-forgot-reset'),

    # Social login
    path('google/login/', GoogleSocialAuthView.as_view(), name='google-login'),

    # Deactivate account
    path('deactivate/', DeactivateAccountView.as_view(), name='deactivate'),
]
