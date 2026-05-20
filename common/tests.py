from django.test import RequestFactory, TestCase, override_settings
from django.http import HttpResponse
from common.models import Country
from common.middleware import MultiCountryMiddleware
from django.utils import translation

@override_settings(ALLOWED_HOSTS=['*'])
class MultiCountryTest(TestCase):
    def setUp(self):
        self.cm = Country.objects.create(
            name="Cameroon", 
            code="CM", 
            slug="cm", 
            currency_code="XAF",
            default_language="fr"
        )
        self.ng = Country.objects.create(
            name="Nigeria", 
            code="NG", 
            slug="ng", 
            currency_code="NGN", 
            default_language="en",
            is_default=True
        )
        self.factory = RequestFactory()
        self.middleware = MultiCountryMiddleware(get_response=lambda r: HttpResponse())

    def test_path_prefix_detection(self):
        # Test Cameroon /cm/
        request = self.factory.get('/cm/api/auth/login/')
        self.middleware(request)
        self.assertEqual(request.country.code, "CM")
        self.assertEqual(request.path_info, "/api/auth/login/")
        self.assertEqual(translation.get_language(), "fr")

        # Test Nigeria /ng/
        request = self.factory.get('/ng/api/auth/login/')
        self.middleware(request)
        self.assertEqual(request.country.code, "NG")
        self.assertEqual(request.path_info, "/api/auth/login/")
        self.assertEqual(translation.get_language(), "en")

    def test_subdomain_detection(self):
        # Test cm.localhost
        request = self.factory.get('/api/auth/login/', HTTP_HOST='cm.localhost')
        self.middleware(request)
        self.assertEqual(request.country.code, "CM")
        self.assertEqual(translation.get_language(), "fr")

    def test_default_fallback(self):
        # Test root domain with no prefix
        request = self.factory.get('/api/auth/login/')
        self.middleware(request)
        self.assertEqual(request.country.code, "NG")
        self.assertEqual(translation.get_language(), "en")
