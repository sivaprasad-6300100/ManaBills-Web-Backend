from django.contrib import admin
from .models import (
    ShopProfile,
    Customer,
    Product,
    Invoice,
    InvoiceItem,
    StockTransaction,
)


@admin.register(ShopProfile)
class ShopProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "shop_name", "owner_name", "shop_type", "gst_enabled", "created_at")
    list_filter = ("shop_type", "gst_enabled", "created_at")
    search_fields = ("shop_name", "owner_name", "mobile", "gst_number")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    
    fieldsets = (
        ("Shop Info", {
            "fields": ("user", "shop_name", "owner_name", "shop_type")
        }),
        ("Contact", {
            "fields": ("mobile", "extra_mobile", "address", "timings")
        }),
        ("GST", {
            "fields": ("gst_enabled", "gst_number")
        }),
        ("Media", {
            "fields": ("logo_url",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "mobile", "user", "created_at")
    list_filter = ("created_at", "user")
    search_fields = ("name", "mobile", "email", "gst_number")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    
    fieldsets = (
        ("Basic Info", {
            "fields": ("user", "name", "mobile", "email")
        }),
        ("Business", {
            "fields": ("gst_number", "address")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "qty", "unit", "selling_price", "is_active", "is_low_stock")
    list_filter = ("is_active", "shop_type", "unit", "created_at")
    search_fields = ("name", "category", "hsn_code")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at", "stock_value")
    
    fieldsets = (
        ("Basic Info", {
            "fields": ("user", "name", "category", "unit", "shop_type")
        }),
        ("Pricing", {
            "fields": ("purchase_price", "selling_price", "making_charges")
        }),
        ("Stock", {
            "fields": ("qty", "min_qty_alert", "is_low_stock", "stock_value")
        }),
        ("Tax & Codes", {
            "fields": ("hsn_code",)
        }),
        ("Clothing Details", {
            "fields": ("clothing_type", "clothing_size", "clothing_color", "clothing_gender"),
            "classes": ("collapse",)
        }),
        ("Hardware Details", {
            "fields": ("hw_brand", "hw_material", "hw_model"),
            "classes": ("collapse",)
        }),
        ("Medical Details", {
            "fields": ("med_company", "med_schedule", "med_expiry", "med_batch"),
            "classes": ("collapse",)
        }),
        ("Gold/Silver Details", {
            "fields": ("gold_purity", "metal_type", "gold_weight"),
            "classes": ("collapse",)
        }),
        ("Status", {
            "fields": ("is_active",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ("amount", "created_at")
    fields = ("product", "name", "qty", "unit", "price", "amount", "is_stock_item")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_id", "customer_name", "total", "status", "payment", "created_at")
    list_filter = ("status", "payment", "is_gst", "created_at")
    search_fields = ("invoice_id", "customer_name", "customer_mobile", "customer_gst")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "balance")
    inlines = [InvoiceItemInline]
    
    fieldsets = (
        ("Invoice", {
            "fields": ("user", "invoice_id", "date")
        }),
        ("Customer", {
            "fields": ("customer", "customer_name", "customer_mobile", "customer_gst")
        }),
        ("Shop", {
            "fields": ("shop_name", "shop_address", "shop_gst"),
            "classes": ("collapse",)
        }),
        ("Amounts", {
            "fields": ("subtotal", "gst_amt", "discount", "advance", "total", "balance")
        }),
        ("Tax & Payment", {
            "fields": ("is_gst", "payment", "status")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "tx_type", "product", "qty", "user", "created_at")
    list_filter = ("tx_type", "created_at", "user")
    search_fields = ("product__name", "note", "invoice__invoice_id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    
    fieldsets = (
        ("Transaction", {
            "fields": ("user", "product", "tx_type", "qty")
        }),
        ("Related", {
            "fields": ("invoice", "note")
        }),
        ("Timestamps", {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )
