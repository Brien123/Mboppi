from rest_framework import generics
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from .serializers import CountrySerializer
from .models import Country


class CountryListView(generics.ListAPIView):
    """View to fetch available countries"""
    permission_classes = [AllowAny]
    serializer_class = CountrySerializer
    queryset = Country.objects.filter(is_active=True)
    pagination_class = None

    @extend_schema(tags=['General'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
