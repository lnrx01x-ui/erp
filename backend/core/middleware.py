from django.core.exceptions import PermissionDenied


class PlatformOwnerAdminMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith("/admin/")
            and request.user.is_authenticated
            and not (
                request.user.is_active
                and request.user.is_superuser
                and request.user.is_platform_owner
            )
        ):
            raise PermissionDenied("Platform owner access is required.")
        return self.get_response(request)
