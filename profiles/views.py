from rest_framework import generics, permissions
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from .models import Document, KYCVerification
from .serializers import (
    ProfileSerializer, KYCDocumentsSerializer, KYCVerificationSerializer,
    ProfileResponseSerializer, KYCDocumentResponseSerializer, KYCVerificationListResponseSerializer,
    KYCSubmitSerializer, BasicKYCSerializer, BasicKYCResponseSerializer
)

@extend_schema_view(
    get=extend_schema(
        tags=['User Profile'],
        summary="Retrieve user profile",
        description="Fetches the profile details of the currently authenticated user.",
        responses={200: ProfileResponseSerializer}
    ),
    put=extend_schema(
        tags=['User Profile'],
        summary="Update user profile",
        description="Updates the profile details of the currently authenticated user.",
        responses={200: ProfileResponseSerializer}
    ),
    patch=extend_schema(
        tags=['User Profile'],
        summary="Partial update user profile",
        description="Partially updates the profile details of the currently authenticated user.",
        responses={200: ProfileResponseSerializer}
    ),
)
class ProfileDetailView(generics.RetrieveUpdateAPIView):
    """
    View to retrieve and update the authenticated user's profile.
    """
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.profile

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": _("Profile retrieved successfully."),
            "data": serializer.data
        })

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response({
            "message": _("Profile updated successfully."),
            "data": serializer.data
        })


@extend_schema_view(
    get=extend_schema(
        tags=['KYC'],
        summary="Retrieve KYC documents",
        description="Fetches the KYC documents associated with the authenticated user.",
        responses={200: KYCDocumentResponseSerializer}
    ),
    put=extend_schema(
        tags=['KYC'],
        summary="Upload/Update KYC documents",
        description="Replaces the KYC documents for the authenticated user.",
        responses={200: KYCDocumentResponseSerializer}
    ),
    patch=extend_schema(
        tags=['KYC'],
        summary="Partial update KYC documents",
        description="Updates specific fields of the user's KYC documentation.",
        responses={200: KYCDocumentResponseSerializer}
    ),
)
class KYCDocumentView(generics.RetrieveUpdateAPIView):
    """
    View to retrieve and upload KYC documents for the authenticated user.
    """
    serializer_class = KYCDocumentsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile = self.request.user.profile
        document, created = Document.objects.get_or_create(profile=profile)
        return document

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": _("KYC documents retrieved successfully."),
            "data": serializer.data
        })

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response({
            "message": _("KYC documents uploaded successfully."),
            "data": serializer.data
        })

@extend_schema(tags=['Verification'], responses={200: KYCVerificationListResponseSerializer})
class KYCVerificationListView(generics.ListAPIView):
    """
    View to list all KYC verification attempts for the authenticated user.
    """
    serializer_class = KYCVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return KYCVerification.objects.filter(profile=self.request.user.profile)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return Response({
                "message": _("KYC verifications retrieved successfully."),
                "data": response.data
            })

        return Response({
            "message": _("KYC verifications retrieved successfully."),
            "data": serializer.data
        })

@extend_schema(
    tags=['Verification'],
    summary="Retrieve latest KYC verification",
    description="Fetches the status and details of the most recent KYC verification attempt.",
    responses={200: KYCVerificationSerializer}
)
class KYCLatestVerificationView(generics.RetrieveAPIView):
    """
    View to retrieve the latest KYC verification status for the authenticated user.
    """
    serializer_class = KYCVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile = self.request.user.profile
        return profile.verifications.order_by('-created_at').first()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance:
            return Response({
                "message": _("No KYC verification attempts found."),
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance)
        return Response({
            "message": _("Latest KYC verification retrieved successfully."),
            "data": serializer.data
        })

class KYCSubmitView(generics.GenericAPIView):
    """
    View to submit KYC documents for verification.
    Validates that all required documents are present.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = KYCSubmitSerializer

    @extend_schema(
        tags=['KYC'],
        summary="Submit KYC for verification",
        description="Uploads KYC documents and submits them for verification.",
        request=KYCDocumentsSerializer,
        responses={200: KYCSubmitSerializer, 400: KYCSubmitSerializer}
    )
    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        document, created = Document.objects.get_or_create(profile=profile)
        
        serializer = KYCDocumentsSerializer(document, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        required_fields = [
            'identification_document_front',
            'identification_document_back',
            'selfie',
            'proof_of_address'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not getattr(document, field):
                missing_fields.append(field)

        if missing_fields:
            return Response({
                "message": _("Required KYC documents are missing. Please provide all documents."),
                "missing_fields": missing_fields
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create or get pending verification
        verification, created = KYCVerification.objects.get_or_create(profile=profile, status='PENDING')

        return Response({
            "message": _("KYC documents submitted successfully. Verification is pending."),
            "status": verification.status
        }, status=status.HTTP_200_OK)

class BasicKYCSubmitView(generics.CreateAPIView):
    """
    View to submit basic KYC questionnaire.
    Sets the user's KYC level to 'basic' upon submission.
    """
    serializer_class = BasicKYCSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['KYC'],
        summary="Submit Basic KYC",
        description="Submits the basic KYC questionnaire and upgrades user to Basic KYC level.",
        responses={201: BasicKYCResponseSerializer}
    )
    def perform_create(self, serializer):
        profile = self.request.user.profile
        serializer.save(profile=profile)
        profile.kyc_level = 'basic'
        profile.save()

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({
            "message": _("Basic KYC submitted successfully. Your spending limit has been increased to $100."),
            "data": response.data
        }, status=status.HTTP_201_CREATED)
