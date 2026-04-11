from rest_framework.permissions import BasePermission

class IsJWTAuthenticated(BasePermission):
    """
    Allows access only to authenticated users with valid JWT
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
