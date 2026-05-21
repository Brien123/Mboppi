from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from .models import OTP
from social_django.utils import load_strategy, load_backend
from social_core.exceptions import AuthException, AuthFailed
from .serializers import (
    UserSerializer, OTPSendSerializer, OTPVerifySerializer,
    LoginSerializer,
    LoginResponseSerializer, RegisterResponseSerializer, LogoutSerializer,
    RefreshTokenSerializer, 
    ChangeEmailRequestSerializer, ChangeEmailConfirmSerializer,
    ChangePasswordSerializer,
    ForgotPasswordRequestSerializer, ForgotPasswordResetSerializer,
    GoogleSocialAuthRequest
)
from common.serializers import SuccessResponseSerializer
from .utils import send_otp_email, send_change_email_otp, send_forgot_password_email

User = get_user_model()

class RegisterView(generics.GenericAPIView):
    """Register a new user and send OTP"""
    permission_classes = [AllowAny]
    serializer_class = UserSerializer

    @extend_schema(request=UserSerializer,responses={201: RegisterResponseSerializer},tags=['Authentication'])
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate OTP
        otp = OTP.generate_otp(user.email)
        send_otp_email(user, otp.code)
        
        return Response(RegisterResponseSerializer({
            "message": _("User registered successfully. OTP sent to your email."),
            "data": UserSerializer(user).data
        }).data, status=status.HTTP_201_CREATED)

class OTPSendView(generics.GenericAPIView):
    """Resend OTP to user's email"""
    permission_classes = [AllowAny]
    serializer_class = OTPSendSerializer

    @extend_schema(responses={200: SuccessResponseSerializer}, tags=['Authentication'])
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()
        
        if not user:
            from allauth.account.models import EmailAddress
            email_address = EmailAddress.objects.filter(email=email).first()
            if email_address:
                user = email_address.user

        if not user:
             return Response(SuccessResponseSerializer({
                "message": _("User with this email does not exist."),
                "data": None
            }).data, status=status.HTTP_404_NOT_FOUND)

        # Generate new OTP
        otp = OTP.generate_otp(email)
        send_otp_email(user, otp.code)
        
        return Response(SuccessResponseSerializer({
            "message": _("OTP sent to your email."),
            "data": None
        }).data, status=status.HTTP_200_OK)

class OTPVerifyView(generics.GenericAPIView):
    """Verify OTP and activate user"""
    permission_classes = [AllowAny]
    serializer_class = OTPVerifySerializer

    @extend_schema(responses={200: LoginResponseSerializer}, tags=['Authentication'])
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        
        try:
            otp = OTP.objects.get(email=email, code=code, is_verified=False)
            
            if not otp.is_valid():
                otp.delete()
                return Response(SuccessResponseSerializer({
                    "message": _("OTP has expired. Please request a new one."),
                    "data": None
                }).data, status=status.HTTP_400_BAD_REQUEST)
            
            otp.is_verified = True
            otp.save()
            user = User.objects.filter(email=email).first()
            if not user:
                from allauth.account.models import EmailAddress
                email_address = EmailAddress.objects.filter(email=email).first()
                if email_address:
                    user = email_address.user
                    
            if user:
                user.is_active = True
                user.save()
                
                # Create/Update allauth EmailAddress
                try:
                    from allauth.account.models import EmailAddress
                    EmailAddress.objects.update_or_create(
                        user=user, 
                        email=email,
                        defaults={'verified': True, 'primary': True}
                    )
                except Exception:
                    pass
            
            refresh = RefreshToken.for_user(user)
            
            return Response(LoginResponseSerializer({
                "message": _("Email verified successfully. You can now login."),
                "data": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": UserSerializer(user).data
                }
            }).data, status=status.HTTP_200_OK)
            
        except OTP.DoesNotExist:
            return Response(SuccessResponseSerializer({
                "message": _("Invalid OTP or email."),
                "data": None
            }).data, status=status.HTTP_400_BAD_REQUEST)

class LoginView(generics.GenericAPIView):
    """Login user and return JWT tokens"""
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @extend_schema(responses={200: LoginResponseSerializer}, tags=['Authentication'])
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        if not user.is_active:
            return Response(SuccessResponseSerializer({
                "message": _("Your email is not verified. Please verify your email first."),
                "data": None
            }).data, status=status.HTTP_403_FORBIDDEN)
        
        refresh = RefreshToken.for_user(user)
        
        return Response(LoginResponseSerializer({
            "message": _("Login successful."),
            "data": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data
            }
        }).data, status=status.HTTP_200_OK)

class LogoutView(generics.GenericAPIView):
    """Logout user"""
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(responses={200: SuccessResponseSerializer}, tags=['Authentication'])
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh_token = serializer.validated_data['refresh_token']
        
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(SuccessResponseSerializer({
                "message": _("Logout successful."),
                "data": None
            }).data, status=status.HTTP_200_OK)
            
        except TokenError as e:
            return Response(SuccessResponseSerializer({
                "message": _("Invalid token."),
                "data": None
            }).data, status=status.HTTP_400_BAD_REQUEST)
            
class RefreshTokenView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = RefreshTokenSerializer

    @extend_schema(responses={200: LoginResponseSerializer}, tags=['Authentication'])
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        refresh_token_str = serializer.validated_data['refresh_token']
        
        try:
            old_refresh = RefreshToken(refresh_token_str)
            user_id = old_refresh['user_id']
            user = User.objects.get(id=user_id)
            new_refresh = RefreshToken.for_user(user)
            old_refresh.blacklist()

            return Response(LoginResponseSerializer({
                "message": _("Token refreshed successfully."),
                "data": {
                    "access": str(new_refresh.access_token),
                    "refresh": str(new_refresh),
                    "user": UserSerializer(user).data
                }
            }).data, status=status.HTTP_200_OK)

        except (TokenError, InvalidToken):
            return Response({
                "message": _("Token is invalid or expired.")
            }, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            return Response({
                "message": _("User not found.")
            }, status=status.HTTP_404_NOT_FOUND)

class ChangeEmailRequestView(generics.GenericAPIView):
    """send OTP to the new email address."""
    permission_classes = [IsAuthenticated]
    serializer_class = ChangeEmailRequestSerializer

    @extend_schema(request=ChangeEmailRequestSerializer,responses={200: SuccessResponseSerializer},tags=['Authentication'],
                    summary="Request email change",description="Send a verification OTP to the new email address. Must be confirmed with /email/change/confirm/.")
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_email = serializer.validated_data['new_email']

        otp = OTP.generate_otp(new_email)
        send_change_email_otp(request.user, new_email, otp.code)

        return Response(SuccessResponseSerializer({
            "message": _("A verification code has been sent to your new email address."),
            "data": None
        }).data, status=status.HTTP_200_OK)

class ChangeEmailConfirmView(generics.GenericAPIView):
    """verify OTP and apply the new email."""
    permission_classes = [IsAuthenticated]
    serializer_class = ChangeEmailConfirmSerializer

    @extend_schema(request=ChangeEmailConfirmSerializer,responses={200: SuccessResponseSerializer},tags=['Authentication'],
                summary="Confirm email change",description="Verify the OTP sent to the new email, then update the account email.")
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_email = serializer.validated_data['new_email']
        code = serializer.validated_data['code']

        try:
            otp = OTP.objects.get(email=new_email, code=code, is_verified=False)

            if not otp.is_valid():
                otp.delete()
                return Response(SuccessResponseSerializer({
                    "message": _("OTP has expired. Please request a new one."),
                    "data": None
                }).data, status=status.HTTP_400_BAD_REQUEST)

            otp.is_verified = True
            otp.save()

            user = request.user
            user.email = new_email
            user.save(update_fields=['email'])

            try:
                from allauth.account.models import EmailAddress
                EmailAddress.objects.filter(user=user).update(primary=False)
                EmailAddress.objects.update_or_create(
                    user=user,
                    email=new_email,
                    defaults={'verified': True, 'primary': True}
                )
            except Exception:
                pass

            return Response(SuccessResponseSerializer({
                "message": _("Email address updated successfully."),
                "data": None
            }).data, status=status.HTTP_200_OK)

        except OTP.DoesNotExist:
            return Response(SuccessResponseSerializer({
                "message": _("Invalid OTP or email."),
                "data": None
            }).data, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(generics.GenericAPIView):
    """Authenticated user changes their own password."""
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: SuccessResponseSerializer},
        tags=['Authentication'],
        summary="Change password",
        description="Change the currently authenticated user's password. Requires the current password for verification."
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])

        return Response(SuccessResponseSerializer({
            "message": _("Password changed successfully."),
            "data": None
        }).data, status=status.HTTP_200_OK)

class ForgotPasswordRequestView(generics.GenericAPIView):
    """unauthenticated user requests a password-reset OTP."""
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordRequestSerializer

    @extend_schema(
        request=ForgotPasswordRequestSerializer,
        responses={200: SuccessResponseSerializer},
        tags=['Authentication'],
        summary="Forgot password request OTP",
        description="Send a password-reset OTP to the registered email. Always returns 200 to avoid user enumeration."
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user = User.objects.filter(email=email, is_active=True).first()
        if not user:
            from allauth.account.models import EmailAddress
            email_address = EmailAddress.objects.filter(email=email, verified=True).first()
            if email_address and email_address.user.is_active:
                user = email_address.user

        if user:
            otp = OTP.generate_otp(email)
            send_forgot_password_email(user, otp.code)

        return Response(SuccessResponseSerializer({
            "message": _("If this email is registered, a password-reset code has been sent."),
            "data": None
        }).data, status=status.HTTP_200_OK)

class ForgotPasswordResetView(generics.GenericAPIView):
    """verify OTP and set the new password."""
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordResetSerializer

    @extend_schema(
        request=ForgotPasswordResetSerializer,
        responses={200: SuccessResponseSerializer},
        tags=['Authentication'],
        summary="Forgot password reset",
        description="Verify the OTP and set a new password for the account."
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['new_password']

        try:
            otp = OTP.objects.get(email=email, code=code, is_verified=False)

            if not otp.is_valid():
                otp.delete()
                return Response(SuccessResponseSerializer({
                    "message": _("OTP has expired. Please request a new one."),
                    "data": None
                }).data, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.filter(email=email, is_active=True).first()
            if not user:
                from allauth.account.models import EmailAddress
                email_address = EmailAddress.objects.filter(email=email, verified=True).first()
                if email_address and email_address.user.is_active:
                    user = email_address.user

            if not user:
                return Response(SuccessResponseSerializer({
                    "message": _("No active account found with this email."),
                    "data": None
                }).data, status=status.HTTP_404_NOT_FOUND)

            otp.is_verified = True
            otp.save()

            user.set_password(new_password)
            user.save(update_fields=['password'])

            return Response(SuccessResponseSerializer({
                "message": _("Password reset successfully. You can now log in."),
                "data": None
            }).data, status=status.HTTP_200_OK)

        except OTP.DoesNotExist:
            return Response(SuccessResponseSerializer({
                "message": _("Invalid OTP or email."),
                "data": None
            }).data, status=status.HTTP_400_BAD_REQUEST)

class GoogleSocialAuthView(generics.GenericAPIView):
    """
    Google OAuth2 social authentication.
    Expects { "access_token": "user_google_token" } in request body.
    Returns JWT tokens (access, refresh) and user data.
    """
    permission_classes = [AllowAny]
    serializer_class = GoogleSocialAuthRequest

    @extend_schema(request=GoogleSocialAuthRequest,responses={200: LoginResponseSerializer},tags=['Authentication'],
                        summary='Google Social Login',description='Authenticate or register using Google OAuth2 token.')
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_token = serializer.validated_data['access_token']

        strategy = load_strategy(request)
        backend = load_backend(
            strategy=strategy,
            name='google-oauth2',
            redirect_uri=None
        )

        try:
            user = backend.do_auth(access_token)
        except (AuthException, AuthFailed) as e:
            return Response(
                {"message": _("Invalid or expired token"), "detail": str(e)},
                status=401
            )
        except Exception as e:
            return Response(
                {"message": _("Authentication failed"), "detail": str(e)},
                status=400
            )

        if not user or not user.is_active:
            return Response(
                {"message": _("User inactive or creation failed")},
                status=403
            )

        refresh = RefreshToken.for_user(user)

        return Response(LoginResponseSerializer({
            "message": _("Google login successful."),
            "data": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data
            }
        }).data, status=200)

class DeactivateAccountView(generics.GenericAPIView):
    """Deactivate user account"""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SuccessResponseSerializer}, tags=['Authentication'])
    def post(self, request):
        user = request.user
        user.is_active = False
        user.save()
        return Response(SuccessResponseSerializer({
            "message": _("Account deactivated successfully."),
            "data": None
        }).data, status=200)