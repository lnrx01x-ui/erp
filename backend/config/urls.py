from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView


admin.site.site_header = "نسق | إدارة المنصة"
admin.site.site_title = "إدارة نسق"
admin.site.index_title = "إدارة الشركات والحسابات"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("organizations.urls")),
    path("api/v1/", include("customers.urls")),
    path("api/v1/", include("products.urls")),
    path("api/v1/", include("inventory.urls")),
    path("api/v1/", include("sales.urls")),
    path("", TemplateView.as_view(template_name="index.html"), name="frontend"),
]
