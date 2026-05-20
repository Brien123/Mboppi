from django.core.cache import cache
from .models import Country, UserDevice
import hashlib
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

def get_cached_country(field, value=None):
    if field == 'slug':
        cache_key = f"country_slug_{value}"
    elif field == 'code':
        cache_key = f"country_code_{value}"
    elif field == 'default':
        cache_key = "country_default"
    else:
        return None
        
    country = cache.get(cache_key)
    if country is None:
        if field == 'slug':
            country = Country.objects.filter(slug=value, is_active=True).first()
        elif field == 'code':
            country = Country.objects.filter(code=value, is_active=True).first()
        elif field == 'default':
            country = Country.objects.filter(is_default=True, is_active=True).first()
            if not country:
                country = Country.objects.filter(is_active=True).first()
                
        if country:
            # Cache for 24 hours
            cache.set(cache_key, country, timeout=86400)
    return country

class MultiCountryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def _get_country_from_user(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            return getattr(getattr(request.user, 'profile', None), 'country', None)
        return None

    def _get_country_from_token(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None
            
        try:
            token = auth_header.split(' ')[1]
            User = get_user_model()
            user = User.objects.get(id=AccessToken(token)['user_id'])
            return getattr(getattr(user, 'profile', None), 'country', None)
        except Exception:
            return None

    def __call__(self, request):
        country = (
            self._get_country_from_user(request) or
            self._get_country_from_token(request) or
            get_cached_country('default')
        )

        request.country = country
        return self.get_response(request)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class DeviceTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not hasattr(request, 'user_agent'):
            return response
            
        ip_address = get_client_ip(request)
        ua_string = request.META.get('HTTP_USER_AGENT', '')
        
        # Create a fingerprint
        fingerprint_data = f"{ip_address}:{ua_string}"
        fingerprint = hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()
        
        user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
        
        if request.user_agent.is_mobile:
            device_type = 'mobile'
        elif request.user_agent.is_tablet:
            device_type = 'tablet'
        elif request.user_agent.is_pc:
            device_type = 'pc'
        elif request.user_agent.is_bot:
            device_type = 'bot'
        else:
            device_type = 'unknown'

        UserDevice.objects.update_or_create(
            fingerprint=fingerprint,
            user=user,
            defaults={
                'device_type': device_type,
                'browser': request.user_agent.browser.family,
                'os': request.user_agent.os.family,
                'device_family': request.user_agent.device.family,
                'ip_address': ip_address,
            }
        )

        return response
