from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Country


class SuccessResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = serializers.DictField(required=False, allow_null=True)

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'slug', 'currency_code', 'exchange_rate', 'default_language', 'is_default']
