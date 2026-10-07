from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.db.models import Q


class EmailOrUsernameBackend(BaseBackend):
    """Mirrors the app's login: a single identity field accepting email OR username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        identity = (username or kwargs.get("email") or "").strip().lower()
        if not identity or not password:
            return None
        try:
            user = UserModel.objects.filter(
                Q(email__iexact=identity) | Q(username__iexact=identity)
            ).first()
        except UserModel.DoesNotExist:
            return None
        if user is None:
            UserModel().set_password(password)  # mitigate timing attacks
            return None
        if not user.check_password(password):
            return None
        if not self.user_can_authenticate(user):
            return None
        return user

    def user_can_authenticate(self, user):
        return getattr(user, "is_active", True)

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
