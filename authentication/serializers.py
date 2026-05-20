from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field

from common.models import Country

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(write_only=True, required=True)
    avatar = serializers.ImageField(write_only=True, required=False)
    country_id = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    is_profile_complete = serializers.SerializerMethodField()
    is_kyc_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'password', 'phone', 'avatar', 'country_id', 'is_active', 'is_staff', 'is_superuser', 'is_profile_complete', 'is_kyc_verified']
        extra_kwargs = {
            'password': {'write_only': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'is_active': {'read_only': True},
            'is_staff': {'read_only': True},
            'is_superuser': {'read_only': True},
            'is_profile_complete': {'read_only': True},
            'is_kyc_verified': {'read_only': True},
        }

    @extend_schema_field(serializers.BooleanField())
    def get_is_profile_complete(self, obj):
        return hasattr(obj, 'profile') and obj.profile.is_complete

    @extend_schema_field(serializers.BooleanField())
    def get_is_kyc_verified(self, obj):
        if not hasattr(obj, 'profile'):
            return False
        latest = obj.profile.latest_verification
        return latest.status == 'APPROVED' if latest else False

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("A user with this email already exists."))
            
        from allauth.account.models import EmailAddress
        if EmailAddress.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("A user with this email already exists."))
            
        return value

    def create(self, validated_data):
        phone = validated_data.pop('phone')
        avatar = validated_data.pop('avatar', None)
        country = validated_data.pop('country_id', None)
        
        username = validated_data['email'].split('@')[0]
        validated_data['username'] = username
        
        user = User.objects.create_user(**validated_data)
        user.is_active = False 
        user.save()

        profile = user.profile
        profile.phone = phone
        if avatar:
            profile.avatar = avatar
        if country:
            profile.country = country
        profile.save()
        
        return user

class OTPSendSerializer(serializers.Serializer):
    email = serializers.EmailField()

class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError(_("Email and password are required."))
        
        user = User.objects.filter(email=email).first()
        if not user:
            from allauth.account.models import EmailAddress
            email_address = EmailAddress.objects.filter(email=email).first()
            if email_address:
                user = email_address.user

        if not user or not user.check_password(password):
            raise serializers.ValidationError(_("Invalid email or password."))
        
        if not user.is_active:
            raise serializers.ValidationError(_("Your email is not verified. Please verify your email first."))
        
        attrs['user'] = user
        return attrs

# SuccessResponseSerializer and SetLanguageSerializer have been moved to common.serializers

class LoginResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = AuthResponseSerializer()

class RegisterResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = UserSerializer()

class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()

# ── Change Email ──────────────────────────────────────────────────────────────

class ChangeEmailRequestSerializer(serializers.Serializer):
    """Step 1: authenticated user submits the new email they want."""
    new_email = serializers.EmailField()

    def validate_new_email(self, value):
        request = self.context.get('request')
        # Must not already be in use
        qs = User.objects.filter(email=value)
        if request and request.user.is_authenticated:
            qs = qs.exclude(pk=request.user.pk)
        if qs.exists():
            raise serializers.ValidationError(_("This email address is already in use."))
            
        from allauth.account.models import EmailAddress
        qs2 = EmailAddress.objects.filter(email=value)
        if request and request.user.is_authenticated:
            qs2 = qs2.exclude(user=request.user)
        if qs2.exists():
            raise serializers.ValidationError(_("This email address is already in use."))
            
        return value

class ChangeEmailConfirmSerializer(serializers.Serializer):
    """Step 2: authenticated user verifies OTP sent to the new email."""
    new_email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

# ── Change Password ───────────────────────────────────────────────────────────

class ChangePasswordSerializer(serializers.Serializer):
    """Authenticated user changes their own password."""
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Current password is incorrect."))
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({"confirm_new_password": _("Passwords do not match.")})
        return attrs

# ── Forgot Password ───────────────────────────────────────────────────────────

class ForgotPasswordRequestSerializer(serializers.Serializer):
    """Step 1: unauthenticated user submits their registered email."""
    email = serializers.EmailField()

class ForgotPasswordResetSerializer(serializers.Serializer):
    """Step 2: submit OTP + new password to complete the reset."""
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({"confirm_new_password": _("Passwords do not match.")})
        return attrs

class GoogleSocialAuthRequest(serializers.Serializer):
    access_token = serializers.CharField(write_only=True)
    