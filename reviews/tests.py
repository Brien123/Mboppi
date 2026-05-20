from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.cache import cache
from common.models import Country
from products.models import Category, Product
from .models import Review

User = get_user_model()

class ReviewsBaseTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Clear cache to prevent stale country data from affecting tests
        cache.clear()
        
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            username='user1',
            password='password123',
            first_name='User',
            last_name='One'
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            username='user2',
            password='password123',
            first_name='User',
            last_name='Two'
        )
        # Create a country to satisfy potential middleware/logging dependencies
        self.country = Country.objects.create(
            name="Test Country",
            code="TC",
            slug="tc",
            currency_code="TCC",
            exchange_rate=500.00,
            default_language="en",
            is_default=True
        )
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            category=self.category,
            name='Test Phone',
            slug='test-phone',
            base_price=10.00,
            stock=50
        )

class ReviewModelTest(ReviewsBaseTest):
    def test_review_creation(self):
        review = Review.objects.create(
            product=self.product,
            user=self.user1,
            rating=5,
            comment="Great product!"
        )
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(str(review), f"Review by {self.user1.email} for {self.product.name}")

    def test_unique_review_per_user_product(self):
        Review.objects.create(product=self.product, user=self.user1, rating=4)
        with self.assertRaises(Exception): # unique_together triggers integrity error at DB level
            Review.objects.create(product=self.product, user=self.user1, rating=5)

    def test_rating_validators(self):
        # We manually call full_clean as Django models don't auto-validate on save()
        review_low = Review(product=self.product, user=self.user1, rating=0)
        with self.assertRaises(ValidationError):
            review_low.full_clean()
        
        review_high = Review(product=self.product, user=self.user1, rating=6)
        with self.assertRaises(ValidationError):
            review_high.full_clean()

class ReviewAPITest(ReviewsBaseTest):
    def setUp(self):
        super().setUp()
        self.review_url = reverse('review-list')

    def test_list_reviews_public(self):
        Review.objects.create(product=self.product, user=self.user1, rating=4)
        response = self.client.get(self.review_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Accessing 'results' because data is paginated
        self.assertEqual(len(response.data['data']['results']), 1)

    def test_filter_reviews_by_product(self):
        product2 = Product.objects.create(
            category=self.category, name='Other', slug='other', base_price=1, stock=1
        )
        Review.objects.create(product=self.product, user=self.user1, rating=4)
        Review.objects.create(product=product2, user=self.user1, rating=5)
        
        response = self.client.get(f"{self.review_url}?product={self.product.id}")
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertEqual(response.data['data']['results'][0]['product'], self.product.id)

    def test_create_review_authenticated(self):
        self.client.force_authenticate(user=self.user1)
        data = {
            "product": self.product.id,
            "rating": 5,
            "comment": "Excellent!"
        }
        response = self.client.post(self.review_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Review.objects.count(), 1)

    def test_update_own_review(self):
        review = Review.objects.create(product=self.product, user=self.user1, rating=4)
        self.client.force_authenticate(user=self.user1)
        url = reverse('review-detail', kwargs={'pk': review.pk})
        data = {"rating": 5, "product": self.product.id} # product is required by the serializer
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)

    def test_cannot_update_others_review(self):
        review = Review.objects.create(product=self.product, user=self.user1, rating=4)
        self.client.force_authenticate(user=self.user2)
        url = reverse('review-detail', kwargs={'pk': review.pk})
        response = self.client.patch(url, {"rating": 1})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

class ProductReviewIntegrationTest(ReviewsBaseTest):
    def test_product_rating_stats(self):
        Review.objects.create(product=self.product, user=self.user1, rating=5)
        Review.objects.create(product=self.product, user=self.user2, rating=3)
        
        url = reverse('product-detail', kwargs={'slug': self.product.slug})
        response = self.client.get(url)
        
        data = response.data['data']
        self.assertEqual(data['average_rating'], 4.0)
        self.assertEqual(data['review_count'], 2)
