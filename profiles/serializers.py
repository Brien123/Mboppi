from rest_framework import serializers
from .models import Profile, Document, KYCVerification, BasicKYCSubmission
from common.serializers import CountrySerializer
from common.models import Country

class BasicKYCSerializer(serializers.ModelSerializer):
    class Meta:
        model = BasicKYCSubmission
        fields = ['full_name', 'birth_date', 'nationality', 'occupation', 'source_of_funds']

class BasicKYCResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = BasicKYCSerializer(required=False)

    
class KYCDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            'identification_document_front',
            'identification_document_back',
            'selfie',
            'proof_of_address',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class KYCVerificationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = KYCVerification
        fields = [
            'id',
            'status',
            'status_display',
            'admin_notes',
            'reviewed_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'status', 'status_display', 'admin_notes', 'reviewed_at', 'created_at', 'updated_at']

class ProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    latest_verification = KYCVerificationSerializer(read_only=True)
    country = CountrySerializer(read_only=True)
    country_id = serializers.PrimaryKeyRelatedField(source='country', queryset=Country.objects.all(), write_only=True, required=False, allow_null=True)
    kyc_spending_limit_usd = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Profile
        fields = [
            'id', 
            'user_email', 
            'user_first_name', 
            'user_last_name', 
            'phone', 
            'birth_date', 
            'avatar', 
            'is_complete',
            'is_kyc_verified',
            'kyc_level',
            'kyc_spending_limit_usd',
            'latest_verification',
            'country',
            'country_id',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'is_complete', 'is_kyc_verified', 'kyc_level', 'kyc_spending_limit_usd', 'latest_verification', 'created_at', 'updated_at']

class ProfileResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = ProfileSerializer()

class KYCDocumentResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = KYCDocumentsSerializer()

class KYCVerificationListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = serializers.DictField(required=False, allow_null=True)

class KYCSubmitSerializer(serializers.Serializer):
    message = serializers.CharField()
    status = serializers.CharField(required=False)
    missing_fields = serializers.ListField(child=serializers.CharField(), required=False)
