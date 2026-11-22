from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Lets people log in with either their username or their email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()
        user = (User.objects.filter(email__iexact=username).first() if "@" in username else None) \
            or User.objects.filter(username__iexact=username).first()
        if user is None:
            User().set_password(password)   # equalise timing so valid usernames are not detectable
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
