from rest_framework import permissions

class IsAdminUserOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        """Check if user has permission to access the view"""
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff