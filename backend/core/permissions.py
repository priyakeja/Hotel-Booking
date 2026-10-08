from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Object level permission: anyone may read, only the owner may write."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner = getattr(obj, 'user', None)
        return owner == request.user or request.user.is_staff


class IsAdminOrReadOnly(permissions.BasePermission):
    """Anyone may read; only staff may create/update/delete."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)
