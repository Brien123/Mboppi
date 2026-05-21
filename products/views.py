from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Count
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import Category, Product, ProductViewLog, ProductSearchLog
from .serializers import (
    CategorySerializer, ProductSerializer,
    CategoryResponseSerializer, CategoryListResponseSerializer,
    ProductResponseSerializer, ProductListResponseSerializer,
    ProductSearchRequestSerializer, SearchSuggestionResponseSerializer,
    SearchSuggestionSerializer, ProductSearchLogResponseSerializer,
    ProductSearchLogSerializer, PopularSearchResponseSerializer, ImageSearchSerializer
)
from .permissions import IsAdminUserOrReadOnly
from .utils import get_client_ip
from .signals import product_search_performed
from .search.elasticsearch_utils import ElasticsearchUtils
from .ml_models.collab_filter import CollaborativeFilteringModel
import logging
import time

logger = logging.getLogger(__name__)
es_utils = ElasticsearchUtils()

_model_cache = None
MODEL_FILEPATH = '/tmp/recommendation_model.pkl'

def get_recommendation_model():
    global _model_cache
    if _model_cache is None:
        _model_cache = CollaborativeFilteringModel.load(MODEL_FILEPATH)
    return _model_cache

def invalidate_recommendation_model_cache():
    """Call this after retraining so the next request picks up the fresh model."""
    global _model_cache
    _model_cache = None


@extend_schema_view(
    list=extend_schema(summary="List all categories", tags=['Products'], responses={200: CategoryListResponseSerializer}),
    retrieve=extend_schema(summary="Retrieve a category", tags=['Products'], responses={200: CategoryResponseSerializer}),
    create=extend_schema(summary="Create a category (Admin only)", tags=['Products'], responses={201: CategoryResponseSerializer}),
    update=extend_schema(summary="Update a category (Admin only)", tags=['Products'], responses={200: CategoryResponseSerializer}),
    partial_update=extend_schema(summary="Partially update a category (Admin only)", tags=['Products'], responses={200: CategoryResponseSerializer}),
    destroy=extend_schema(summary="Delete a category (Admin only)", tags=['Products']),
)
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUserOrReadOnly]
    lookup_field = 'id'

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return Response({"message": _("Categories retrieved successfully."), "data": response.data})
        serializer = self.get_serializer(queryset, many=True)
        return Response({"message": _("Categories retrieved successfully."), "data": serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"message": _("Category retrieved successfully."), "data": serializer.data})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"message": _("Category created successfully."), "data": serializer.data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({"message": _("Category updated successfully."), "data": serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": _("Category deleted successfully."), "data": None}, status=status.HTTP_204_NO_CONTENT)

    @extend_schema(summary="Get products for a specific category", tags=['Products'], responses={200: ProductListResponseSerializer})
    @action(detail=True, methods=['get'])
    def products(self, request, id=None):
        category = self.get_object()
        if request.user and request.user.is_staff:
            products = Product.objects.filter(category=category)
        else:
            products = Product.objects.filter(category=category, is_active=True)
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response({"message": _("Category products retrieved successfully."), "data": serializer.data})


@extend_schema_view(
    list=extend_schema(summary="List all products", tags=['Products'], responses={200: ProductListResponseSerializer}),
    retrieve=extend_schema(summary="Retrieve a product", tags=['Products'], responses={200: ProductResponseSerializer}),
    create=extend_schema(summary="Create a product (Admin only)", tags=['Products'], responses={201: ProductResponseSerializer}),
    update=extend_schema(summary="Update a product (Admin only)", tags=['Products'], responses={200: ProductResponseSerializer}),
    partial_update=extend_schema(summary="Partially update a product (Admin only)", tags=['Products'], responses={200: ProductResponseSerializer}),
    destroy=extend_schema(summary="Delete a product (Admin only)", tags=['Products']),
)
class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUserOrReadOnly]
    lookup_field = 'id'

    def get_queryset(self):
        if self.request.user and self.request.user.is_staff:
            return Product.objects.all().select_related('category').prefetch_related('product_images')
        return Product.objects.filter(is_active=True).select_related('category').prefetch_related('product_images')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return Response({"message": _("Products retrieved successfully."), "data": response.data})
        serializer = self.get_serializer(queryset, many=True)
        return Response({"message": _("Products retrieved successfully."), "data": serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        country = getattr(request, 'country', None)
        user = request.user if request.user.is_authenticated else None
        ProductViewLog.objects.create(product=instance,country=country,user=user,ip_address=get_client_ip(request))
        serializer = self.get_serializer(instance)
        return Response({"message": _("Product retrieved successfully."), "data": serializer.data})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"message": _("Product created successfully."), "data": serializer.data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({"message": _("Product updated successfully."), "data": serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": _("Product deleted successfully."), "data": None}, status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Search products with filters and sorting",
        tags=['Products'],
        parameters=[ProductSearchRequestSerializer],
        responses={200: ProductListResponseSerializer}
    )
    @action(detail=False, methods=['get'])
    def search(self, request):
        request_serializer = ProductSearchRequestSerializer(data=request.query_params)
        request_serializer.is_valid(raise_exception=True)
        params = request_serializer.validated_data

        query = params.get('q', '')
        min_price = params.get('min_price')
        max_price = params.get('max_price')
        ordering = params.get('ordering', 'relevance')

        if min_price is not None:
            min_price = min_price/request.country.exchange_rate if hasattr(request, 'country') and request.country else 1
        
        if max_price is not None:
            max_price = max_price/request.country.exchange_rate if hasattr(request, 'country') and request.country else 1


        page_num = int(request.query_params.get('page', 1))
        page_size = 10

        es_response = es_utils.product_search(query=query, page=page_num, size=page_size, sort=ordering, min_price=min_price, max_price=max_price)

        if not es_response:
            return Response({"message": _("Search service unavailable."), "data": []}, status=503)

        hits = es_response['hits']['hits']
        total_count = es_response['hits']['total']['value']
        product_ids = [hit['_id'] for hit in hits]

        queryset = Product.objects.filter(id__in=product_ids).select_related('category').prefetch_related('product_images')
        
        preserved = {str(pk): pos for pos, pk in enumerate(product_ids)}
        sorted_queryset = sorted(queryset, key=lambda obj: preserved.get(str(obj.id)))

        serializer = self.get_serializer(sorted_queryset, many=True, context={'request': request})
        product_search_performed.send(sender=self.__class__, user=request.user if request.user.is_authenticated else None, country=getattr(request, 'country', None), query=query)
        
        return Response({
            "message": _("Search results retrieved successfully."),
            "data": {
                "count": total_count,
                "next": self.get_next_link() if (page_num * page_size) < total_count else None,
                "previous": self.get_previous_link() if page_num > 1 else None,
                "results": serializer.data
            }
        })

    @extend_schema(
        summary="Get top trending products (last 7 days)",
        tags=['Products'],
        responses={200: ProductListResponseSerializer}
    )
    @action(detail=False, methods=['get'])
    def trending(self, request):
        country = getattr(request, 'country', None)
        # 7-day time window for trending calculation
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        count_filter = Q(view_logs__viewed_at__gte=seven_days_ago)
        if country:
            count_filter &= Q(view_logs__country=country)
        
        trending_products = Product.objects.filter(is_active=True).annotate(
            view_count=Count('view_logs', filter=count_filter)
        ).filter(view_count__gt=0).order_by('-view_count')

        # Fallback to global trending if country-specific is empty
        if not trending_products.exists() and country:
            count_filter_global = Q(view_logs__viewed_at__gte=seven_days_ago)
            trending_products = Product.objects.filter(is_active=True).annotate(
                view_count=Count('view_logs', filter=count_filter_global)
            ).filter(view_count__gt=0).order_by('-view_count')
            logger.info(f"No trending products for {country}, falling back to global.")

        page = self.paginate_queryset(trending_products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return Response({"message": _("Trending products retrieved successfully."), "data": response.data})

        serializer = self.get_serializer(trending_products, many=True)
        return Response({"message": _("Trending products retrieved successfully."), "data": serializer.data})

    @extend_schema(
        summary="Get search suggestions",
        description="Returns product suggestions (ID, Name, Slug) powered by Elasticsearch.",
        tags=['Products'],
        parameters=[
            OpenApiParameter(name='q', description='Search query', required=True, type=str),
        ],
        responses={200: SearchSuggestionResponseSerializer}
    )
    @action(detail=False, methods=['get'])
    def suggestions(self, request):
        query = request.query_params.get('q', '')
        if len(query) < 2:
            return Response({"message": _("Query too short."), "data": []})

        es_utils = ElasticsearchUtils()
        suggested_data = es_utils.get_suggestions(query, size=10)

        if not suggested_data:
            return Response({"message": _("No suggestions found."), "data": []})

        serializer = SearchSuggestionSerializer(suggested_data, many=True)
        
        return Response({
            "message": _("Suggestions retrieved successfully."), 
            "data": serializer.data
        })

    @extend_schema(
        summary="Get recent searches",
        description="Returns the last 10 search queries performed by the authenticated user.",
        tags=['Products'],
        responses={200: ProductSearchLogResponseSerializer}
    )
    @action(detail=False, methods=['get'])
    def recent_searches(self, request):
        if not request.user.is_authenticated:
            return Response({"message": _("Authentication required."), "data": []}, status=status.HTTP_401_UNAUTHORIZED)

        searches = ProductSearchLog.objects.filter(user=request.user).order_by('-created_at')[:10]
        serializer = ProductSearchLogSerializer(searches, many=True)
        return Response({"message": _("Recent searches retrieved successfully."), "data": serializer.data})

    @extend_schema(
        summary="Get popular searches",
        description="Returns the top 10 most frequent search queries.",
        tags=['Products'],
        responses={200: PopularSearchResponseSerializer}
    )
    @action(detail=False, methods=['get'])
    def popular_searches(self, request):
        country = getattr(request, 'country', None)
        queryset = ProductSearchLog.objects.values('query').annotate(count=Count('query')).order_by('-count')

        if country:
            queryset = queryset.filter(country=country)

        popular = queryset[:10]
        return Response({"message": _("Popular searches retrieved successfully."), "data": list(popular)})

    @extend_schema(
        summary="Get recommended products",
        description="Fast recommendations from pre-trained collaborative filtering model with freshness boosting.",
        tags=['Products'],
        responses={200: ProductListResponseSerializer}
    )
    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        user = request.user if request.user.is_authenticated else None
        start_time = time.time()

        if not user:
            return self.trending(request)

        model = get_recommendation_model()

        if not model:
            logger.warning("Recommendation model not available, falling back to trending")
            return self.trending(request)

        viewed_product_ids = set(
            ProductViewLog.objects.filter(user=user)
            .values_list('product_id', flat=True)
        )

        recommended_ids = model.get_recommendations(
            user_id=str(user.id),
            num_recommendations=30,
            exclude_ids=viewed_product_ids
        )

        if not recommended_ids:
            logger.info(f"No model recommendations for user {user.id}, using trending")
            return self.trending(request)

        queryset = self.get_queryset().filter(id__in=recommended_ids)

        week_ago = timezone.now() - timedelta(days=7)

        scored_products = []
        for product in queryset:
            base_score = 30 - recommended_ids.index(str(product.id))

            if product.created_at > week_ago:
                base_score *= 1.2

            recent_views = product.view_logs.filter(
                viewed_at__gte=week_ago
            ).count()

            if recent_views > 5:
                base_score *= 1.1

            scored_products.append((product, base_score))

        scored_products.sort(key=lambda x: x[1], reverse=True)
        final_queryset = [p for p, _ in scored_products]

        page = self.paginate_queryset(final_queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            duration = time.time() - start_time
            logger.debug(f"Recommendations for user {user.id}: {len(page)} items in {duration:.3f}s")
            return Response({
                "message": _("Recommendations retrieved successfully."),
                "data": response.data
            })

        serializer = self.get_serializer(final_queryset, many=True)
        duration = time.time() - start_time
        logger.debug(f"Recommendations for user {user.id}: {len(final_queryset)} items in {duration:.3f}s")
        return Response({
            "message": _("Recommendations retrieved successfully."),
            "data": serializer.data
        })
    

    @extend_schema(
        summary="Get visually similar products",
        description="Uses CLIP embeddings and Cosine Similarity to find products similar to the given ID.",
        tags=['Products'],
        responses={200: ProductListResponseSerializer}
    )
    @action(detail=True, methods=['get'])
    def similar(self, request, pk=None, **kwargs):
        lookup_value = pk or kwargs.get('id')
        page_num = int(request.query_params.get('page', 1))
        page_size = 10

        es_response = es_utils.get_similar_products(product_id=str(lookup_value), page=page_num, size=page_size)

        if not es_response or not es_response['hits']['hits']:
            return Response({
                "message": _("No similar products found."), 
                "data": {"count": 0, "next": None, "previous": None, "results": []}
            })

        hits = es_response['hits']['hits']
        total_count = es_response['hits']['total']['value']
        product_ids = [hit['_id'] for hit in hits]

        # Hydrate objects from DB in a single query
        queryset = Product.objects.filter(id__in=product_ids).select_related('category').prefetch_related('product_images')
        
        # Re-sort the database results to match ES similarity ranking
        preserved_order = {str(uid): index for index, uid in enumerate(product_ids)}
        sorted_queryset = sorted(queryset, key=lambda x: preserved_order.get(str(x.id)))

        serializer = self.get_serializer(sorted_queryset, many=True, context={'request': request})
        
        return Response({
            "message": _("Similar products retrieved successfully."),
            "data": {
                "count": total_count,
                "next": self.get_next_link() if (page_num * page_size) < total_count else None,
                "previous": self.get_previous_link() if page_num > 1 else None,
                "results": serializer.data
            }
        })


    @extend_schema(
        summary="Search by image",
        description="Upload an image to find products that are visually similar.",
        tags=['Products'],
        request={
            'multipart/form-data': ImageSearchSerializer
        },
        responses={200: ProductListResponseSerializer}
    )
    @action(detail=False, methods=['post'], url_path='image-search')
    def image_search(self, request):
        serializer = ImageSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        uploaded_image = serializer.validated_data['image']
        page_num = int(request.query_params.get('page', 1))
        page_size = 10

        from .search.feature_extraction import CLIPFeatureExtractor
        extractor = CLIPFeatureExtractor()
        
        query_vector = extractor.encode_image(uploaded_image)

        if not query_vector or len(query_vector) != 512:
            return Response({"message": _("Could not process image."), "data": []}, status=400)

        es_response = es_utils.search_by_image(query_vector=query_vector, page=page_num, size=page_size)

        if not es_response or not es_response['hits']['hits']:
            return Response({
                "message": _("No visually similar products found."), 
                "data": {"count": 0, "next": None, "previous": None, "results": []}
            })

        hits = es_response['hits']['hits']
        total_count = es_response['hits']['total']['value']
        product_ids = [hit['_id'] for hit in hits]

        queryset = Product.objects.filter(id__in=product_ids).select_related('category').prefetch_related('product_images')
        
        preserved_order = {str(uid): index for index, uid in enumerate(product_ids)}
        sorted_queryset = sorted(queryset, key=lambda x: preserved_order.get(str(x.id)))

        results_serializer = self.get_serializer(sorted_queryset, many=True, context={'request': request})
        
        return Response({
            "message": _("Image search results retrieved successfully."),
            "data": {
                "count": total_count,
                "next": self.get_next_link() if (page_num * page_size) < total_count else None,
                "previous": self.get_previous_link() if page_num > 1 else None,
                "results": results_serializer.data
            }
        })
