from django.contrib import admin
from django.db.models import Sum

from .models import Invoice, InvoiceLine, PaymentCollection


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="سجّل التحصيل")
    def collected_by(self, obj):
        return obj.actor.email if obj.actor_id else obj.actor_email_snapshot or "مستخدم غير معروف"


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    can_delete = False
    fields = (
        "position",
        "product",
        "product_name",
        "quantity",
        "unit_price",
        "line_total",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "number",
        "organization",
        "customer",
        "issue_date",
        "total",
        "amount_collected",
        "balance_due",
        "payment_status",
        "created_by",
        "issued_at",
    )
    list_filter = ("organization", "issue_date")
    search_fields = ("number", "customer__name", "organization__name")
    date_hierarchy = "issue_date"
    readonly_fields = (
        "id",
        "organization",
        "number",
        "customer",
        "warehouse",
        "issue_date",
        "total",
        "actor",
        "actor_email_snapshot",
        "issued_at",
    )
    inlines = (InvoiceLineInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            admin_collected_total=Sum("payments__amount"),
        )

    @admin.display(description="المحصل")
    def amount_collected(self, obj):
        return obj.admin_collected_total or 0

    @admin.display(description="المتبقي")
    def balance_due(self, obj):
        return obj.total - (obj.admin_collected_total or 0)

    @admin.display(description="الحالة")
    def payment_status(self, obj):
        collected = obj.admin_collected_total or 0
        if collected >= obj.total:
            return "مسددة"
        if collected > 0:
            return "مسددة جزئيًا"
        return "مستحقة"

    @admin.display(description="أنشأها")
    def created_by(self, obj):
        return obj.actor.email if obj.actor_id else obj.actor_email_snapshot or "مستخدم غير معروف"


@admin.register(InvoiceLine)
class InvoiceLineAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "invoice",
        "position",
        "product_name",
        "quantity",
        "unit_price",
        "line_total",
    )
    list_filter = ("invoice__organization",)
    search_fields = ("invoice__number", "product_name")
    readonly_fields = (
        "id",
        "invoice",
        "product",
        "product_name",
        "position",
        "quantity",
        "unit_price",
        "line_total",
    )


@admin.register(PaymentCollection)
class PaymentCollectionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "invoice",
        "organization",
        "amount",
        "method",
        "collected_by",
        "collected_at",
    )
    list_filter = ("organization", "method", "collected_at")
    search_fields = ("invoice__number", "invoice__customer__name", "note")
    date_hierarchy = "collected_at"
    readonly_fields = (
        "id",
        "organization",
        "invoice",
        "amount",
        "method",
        "note",
        "actor",
        "actor_email_snapshot",
        "collected_at",
    )
