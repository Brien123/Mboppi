from django.contrib.auth import get_user_model
from profiles.models import Profile

User = get_user_model()

def create_profile(strategy, details, user=None, *args, **kwargs):
    """Create a Profile for the user if it doesn't exist."""
    if user and not hasattr(user, 'profile'):
        Profile.objects.create(user=user)

def associate_by_email(strategy, details, user=None, *args, **kwargs):
    """
    If a user with the same email already exists (and no social user is linked yet),
    associate this social login with that existing user instead of creating a new one.
    """
    if user:
        return None

    email = details.get('email')
    if not email:
        return None

    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        return {'user': existing_user}
    
    return None