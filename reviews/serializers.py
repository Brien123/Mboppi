from rest_framework import serializers
from .models import Review
from django.utils.translation import gettext_lazy as _

class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_avatar = serializers.ImageField(source='user.profile.avatar', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'product', 'user', 'user_name', 'user_avatar', 
            'rating', 'comment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

class ReviewCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['product', 'rating', 'comment']

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        product = attrs.get('product')

        # For creation, check if a review already exists
        if not self.instance and Review.objects.filter(product=product, user=user).exists():
            raise serializers.ValidationError(_("You have already reviewed this product."))
        
        return attrs

class ReviewResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = ReviewSerializer()

class PaginatedReviewDataSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ReviewSerializer(many=True)

class ReviewListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = PaginatedReviewDataSerializer()
