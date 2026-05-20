from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import Review
from .serializers import (
    ReviewSerializer, ReviewCreateUpdateSerializer,
    ReviewResponseSerializer, ReviewListResponseSerializer
)

@extend_schema_view(
    list=extend_schema(
        summary="List reviews",
        tags=['Reviews'],
        parameters=[
            OpenApiParameter("product", type=int, description="Filter by product ID")
        ],
        responses={200: ReviewListResponseSerializer}
    ),
    retrieve=extend_schema(summary="Retrieve a review", tags=['Reviews'], responses={200: ReviewResponseSerializer}),
    create=extend_schema(summary="Create a review", tags=['Reviews'], responses={201: ReviewResponseSerializer}),
    update=extend_schema(summary="Update a review", tags=['Reviews'], responses={200: ReviewResponseSerializer}),
    partial_update=extend_schema(summary="Partially update a review", tags=['Reviews'], responses={200: ReviewResponseSerializer}),
    destroy=extend_schema(summary="Delete a review", tags=['Reviews']),
)
class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.filter(is_active=True)
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ReviewCreateUpdateSerializer
        return ReviewSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ReviewSerializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return Response({
                "message": _("Reviews retrieved successfully."),
                "data": response.data
            })
        
        serializer = ReviewSerializer(queryset, many=True)
        return Response({
            "message": _("Reviews retrieved successfully."),
            "data": serializer.data
        })

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ReviewSerializer(instance)
        return Response({
            "message": _("Review retrieved successfully."),
            "data": serializer.data
        })

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Return full serialized object
        full_serializer = ReviewSerializer(serializer.instance)
        return Response({
            "message": _("Review created successfully."),
            "data": full_serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if instance.user != request.user:
            return Response({"detail": _("You do not have permission to edit this review.")}, status=status.HTTP_403_FORBIDDEN)
            
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        full_serializer = ReviewSerializer(instance)
        return Response({
            "message": _("Review updated successfully."),
            "data": full_serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"detail": _("You do not have permission to delete this review.")}, status=status.HTTP_403_FORBIDDEN)
        
        self.perform_destroy(instance)
        return Response({
            "message": _("Review deleted successfully."),
            "data": None
        }, status=status.HTTP_204_NO_CONTENT)
