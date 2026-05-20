from rest_framework import permissions
from django.utils.translation import gettext_lazy as _

class IsProfileComplete(permissions.BasePermission):
    """
    Permission check for complete profile.
    """
    message = _('Please complete your profile details to access this feature.')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return hasattr(request.user, 'profile') and request.user.profile.is_complete

class HasPassedKYC(permissions.BasePermission):
    """
    Permission check for any level of KYC (basic or enhanced).
    """
    message = _('Please complete your KYC to access this feature.')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return request.user.profile.kyc_level in ['basic', 'enhanced']

class HasEnhancedKYC(permissions.BasePermission):
    """
    Permission check for enhanced KYC level.
    """
    message = _('Please complete document verification to access this high-limit feature.')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return request.user.profile.kyc_level == 'enhanced'
