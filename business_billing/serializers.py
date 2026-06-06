from rest_framework import serializers
from django.db import transaction as db_transaction
from .models import ShopProfile, Customer, Product, Invoice, InvoiceItem, StockTransaction
from rest_framework import serializers
from .models import Invoice, InvoiceItem



# ═══════════════════════════════════════════════════════════════
#   SHOP PROFILE
# ═══════════════════════════════════════════════════════════════
class ShopProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model  = ShopProfile
        fields = [
            "id", "shop_name", "owner_name", "mobile", "extra_mobile",
            "address", "shop_type", "timings",
            "gst_enabled", "gst_number", "logo_url",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ═══════════════════════════════════════════════════════════════
#   CUSTOMER
# ═══════════════════════════════════════════════════════════════
class CustomerSerializer(serializers.ModelSerializer):

    class Meta:
        model  = Customer
        fields = [
            "id", "name", "mobile", "email",
            "gst_number", "address",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ═══════════════════════════════════════════════════════════════
#   PRODUCT  (Stock)
# ═══════════════════════════════════════════════════════════════
class ProductSerializer(serializers.ModelSerializer):

    is_low_stock = serializers.BooleanField(read_only=True)
    stock_value  = serializers.FloatField(read_only=True)
    purchase_date = serializers.DateField(required=False, allow_null=True)
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Auto-fill purchase_gst if it's 0 but price+rate exist
        if float(data.get('purchase_gst') or 0) == 0:
            pp   = float(data.get('purchase_price') or 0)
            rate = float(data.get('gst_rate') or 0)
            if pp > 0 and rate > 0:
                data['purchase_gst'] = round(pp * rate / 100, 2)
        return data

    class Meta:
        model  = Product
        fields = [
            # Core
            "id", "name", "category", "unit",
            "purchase_price", "selling_price",
            "qty", "min_qty_alert", "hsn_code",
            "gst_rate", "purchase_gst",          # ← ADD
            "supplier_gstin", "purchase_invoice", # ← ADD
            "purchase_date", "sale_type",         # ← ADD
            "gst_inclusive", 
            "shop_type", "is_active",

            # Clothing
            "clothing_type", "clothing_size", "clothing_color", "clothing_gender",

            # Hardware
            "hw_brand", "hw_material", "hw_model",

            # Medical
            "med_company", "med_schedule", "med_expiry", "med_batch",

            # Gold / Silver
            "gold_purity", "metal_type", "gold_weight", "making_charges",

            # Computed
            "is_low_stock", "stock_value",

            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_low_stock", "stock_value", "created_at", "updated_at"]


class ProductLowStockSerializer(serializers.ModelSerializer):
    """Lightweight serializer for low-stock alerts"""

    class Meta:
        model  = Product
        fields = ["id", "name", "qty", "min_qty_alert", "unit", "category"]


class ProductStatsSerializer(serializers.Serializer):
    """Aggregated stock stats for dashboard"""

    total_items      = serializers.IntegerField()
    total_qty        = serializers.FloatField()
    total_value      = serializers.FloatField()
    low_stock_count  = serializers.IntegerField()


# ═══════════════════════════════════════════════════════════════
#   INVOICE ITEM
# ═══════════════════════════════════════════════════════════════
class InvoiceItemSerializer(serializers.ModelSerializer):

    class Meta:
        model  = InvoiceItem
        fields = [
            "id", "product", "name", "qty",
            "price", "unit", "amount", "is_stock_item",
            "gst_rate",
        ]
        read_only_fields = ["id", "amount"]


# ═══════════════════════════════════════════════════════════════
#   INVOICE — Read
# ═══════════════════════════════════════════════════════════════
class InvoiceReadSerializer(serializers.ModelSerializer):

    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model  = Invoice
        fields = [
            "id", "invoice_id",
            "customer", "customer_name", "customer_mobile", "customer_gst",
            "shop_name", "shop_address", "shop_gst",
            "subtotal", "gst_amt", "discount", "advance",
            "total", "balance",
            "is_gst", "payment", "status",
            "date", "created_at", "updated_at",
            "items",
        ]
        read_only_fields = ["id", "balance", "status", "created_at", "updated_at"]


# ═══════════════════════════════════════════════════════════════
#   INVOICE — Create / Update
#   Accepts nested items list, handles stock deduction atomically
# ═══════════════════════════════════════════════════════════════
class InvoiceItemWriteSerializer(serializers.Serializer):
    """Used inside InvoiceWriteSerializer for nested items"""

    product      = serializers.PrimaryKeyRelatedField(
                       queryset=Product.objects.all(), required=False, allow_null=True
                   )
    name         = serializers.CharField(max_length=255)
    qty          = serializers.DecimalField(max_digits=10, decimal_places=2)
    price        = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit         = serializers.CharField(max_length=20, default="piece")
    is_stock_item= serializers.BooleanField(default=False)
    gst_rate     = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)

class InvoiceWriteSerializer(serializers.ModelSerializer):

    items = InvoiceItemWriteSerializer(many=True, write_only=True)

    class Meta:
        model  = Invoice
        fields = [
            "invoice_id",
            "customer",
            "customer_name", "customer_mobile", "customer_gst",
            "shop_name", "shop_address", "shop_gst",
            "subtotal", "gst_amt", "discount", "advance",
            "total",
            "is_gst", "payment",
            "date",
            "items",
        ]

    # ── Validation ────────────────────────────────────────────
    def validate(self, data):
        items = data.get("items", [])

        if not items:
            raise serializers.ValidationError({"items": "At least one item is required."})
        
        # ★ Recalculate gst_amt from per-item rates
        computed_gst = sum(
            float(i["qty"]) * float(i["price"]) * float(i.get("gst_rate", 0)) / 100
            for i in items
        )
        data["gst_amt"] = round(computed_gst, 2)

        
        # Validate stock availability BEFORE saving anything
        errors = []
        for item in items:
            product = item.get("product")
            if product and item.get("is_stock_item"):
                need = item["qty"]
                if product.qty < need:
                    errors.append(
                        f'"{product.name}" — only {product.qty} {product.unit} available, '
                        f'you need {need}.'
                    )
        if errors:
            raise serializers.ValidationError({"stock": errors})

        return data

    # ── Create ────────────────────────────────────────────────
    @db_transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        user       = self.context["request"].user

        invoice = Invoice.objects.create(user=user, **validated_data)

        self._save_items_and_deduct_stock(invoice, items_data, user)
        return invoice

    # ── Update ────────────────────────────────────────────────
    @db_transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            # Remove old items (do NOT re-deduct — only new items deduct)
            instance.items.all().delete()
            self._save_items_and_deduct_stock(instance, items_data, instance.user)

        return instance

    # ── Private helper ────────────────────────────────────────
    def _save_items_and_deduct_stock(self, invoice, items_data, user):
        for item_data in items_data:
            product      = item_data.get("product")
            is_stock_item= item_data.get("is_stock_item", False)

            InvoiceItem.objects.create(
                invoice      = invoice,
                product      = product,
                name         = item_data["name"],
                qty          = item_data["qty"],
                price        = item_data["price"],
                unit         = item_data.get("unit", "piece"),
                is_stock_item= is_stock_item,
                gst_rate      = item_data.get("gst_rate", 0),
            )

            # Auto-deduct stock
            if product and is_stock_item:
                product.qty -= item_data["qty"]
                product.save(update_fields=["qty", "updated_at"])

                StockTransaction.objects.create(
                    user     = user,
                    product  = product,
                    invoice  = invoice,
                    tx_type  = "DEDUCTION",
                    qty      = item_data["qty"],
                    note     = f"Sold via invoice {invoice.invoice_id}",
                )


# ═══════════════════════════════════════════════════════════════
#   MARK-PAID  (PATCH only)
# ═══════════════════════════════════════════════════════════════
class MarkPaidSerializer(serializers.ModelSerializer):

    class Meta:
        model  = Invoice
        fields = ["advance", "status", "balance"]
        read_only_fields = ["status", "balance"]


# ═══════════════════════════════════════════════════════════════
#   STOCK TRANSACTION  (read-only log)
# ═══════════════════════════════════════════════════════════════
class StockTransactionSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(source="product.name", read_only=True)
    invoice_id   = serializers.CharField(source="invoice.invoice_id", read_only=True, allow_null=True)

    class Meta:
        model  = StockTransaction
        fields = [
            "id", "product", "product_name",
            "invoice", "invoice_id",
            "tx_type", "qty", "note",
            "created_at",
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════
#   GST REPORT  — one row per month
# ═══════════════════════════════════════════════════════════════
class GstMonthReportSerializer(serializers.Serializer):

    month         = serializers.CharField()     # "January"
    invoice_count = serializers.IntegerField()
    taxable_value = serializers.FloatField()
    gst_collected = serializers.FloatField()
    total_value   = serializers.FloatField()


# ═══════════════════════════════════════════════════════════════
#   DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════
    # -------------------------------
    # ----------------------
    # ------------
    """
Add these serializers to business_billing/serializers.py
"""
from rest_framework import serializers
from .models import ShopScanner, ShopProfile, Product, CustomerOrder, CustomerOrderItem, ShopNotification
from decimal import Decimal


class ShopScannerSerializer(serializers.ModelSerializer):
    qr_url = serializers.SerializerMethodField()

    class Meta:
        model  = ShopScanner
        fields = ["id", "scanner_id", "is_active", "scan_count", "qr_url", "created_at"]
        read_only_fields = ["id", "scanner_id", "scan_count", "qr_url", "created_at"]

    def get_qr_url(self, obj):
        request = self.context.get("request")
        if request:
            scheme = "https" if request.is_secure() else "http"
            host = request.META.get("HTTP_HOST", "").replace(":8000", ":3000")
            return f"{scheme}://{host}/shop/{obj.scanner_id}"
        return f"https://manabills.in/shop/{obj.scanner_id}"
    

    
class PublicShopSerializer(serializers.ModelSerializer):
    """Minimal shop info for public QR page — no sensitive data"""
    class Meta:
        model  = ShopProfile
        fields = ["shop_name", "owner_name", "address", "shop_type", "timings", "logo_url"]


class PublicProductSerializer(serializers.ModelSerializer):
    """Products shown to customer — only what they need"""
    class Meta:
        model  = Product
        fields = ["id", "name", "category", "unit", "selling_price", "qty", "min_qty_alert"]


class CustomerOrderItemWriteSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    qty        = serializers.DecimalField(max_digits=10, decimal_places=2)


class CustomerOrderWriteSerializer(serializers.Serializer):
    customer_name   = serializers.CharField(max_length=255)
    customer_mobile = serializers.CharField(max_length=15)
    advance         = serializers.DecimalField(max_digits=12, decimal_places=2)
    items           = CustomerOrderItemWriteSerializer(many=True)

    def validate(self, data):
        scanner  = self.context["scanner"]
        items    = data.get("items", [])
        advance  = data.get("advance", Decimal("0"))

        if not items:
            raise serializers.ValidationError({"items": "At least one item required."})
        if advance < Decimal("10"):
            raise serializers.ValidationError({"advance": "Minimum advance is ₹10."})

        # Validate products belong to this shop and have stock
        errors = []
        for item in items:
            try:
                product = Product.objects.get(id=item["product_id"], user=scanner.user, is_active=True)
                if product.qty < item["qty"]:
                    errors.append(f'"{product.name}": only {product.qty} {product.unit} available.')
            except Product.DoesNotExist:
                errors.append(f'Product ID {item["product_id"]} not found.')

        if errors:
            raise serializers.ValidationError({"stock": errors})

        return data

    def create(self, validated_data):
        scanner  = self.context["scanner"]
        items    = validated_data.pop("items")
        advance  = validated_data["advance"]

        # Calculate subtotal
        subtotal = Decimal("0")
        product_map = {}
        for item in items:
            product = Product.objects.get(id=item["product_id"])
            product_map[item["product_id"]] = product
            subtotal += product.selling_price * item["qty"]

        if advance > subtotal:
            raise serializers.ValidationError({"advance": "Advance cannot exceed total."})

        order = CustomerOrder.objects.create(
            user            = scanner.user,
            scanner         = scanner,
            customer_name   = validated_data["customer_name"],
            customer_mobile = validated_data["customer_mobile"],
            subtotal        = subtotal,
            advance         = advance,
            status          = "new",
        )

        # Create order items
        for item in items:
            product = product_map[item["product_id"]]
            CustomerOrderItem.objects.create(
                order   = order,
                product = product,
                name    = product.name,
                qty     = item["qty"],
                price   = product.selling_price,
                unit    = product.unit,
            )

        return order


class CustomerOrderItemReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CustomerOrderItem
        fields = ["id", "name", "qty", "price", "unit", "amount"]


class CustomerOrderReadSerializer(serializers.ModelSerializer):
    items = CustomerOrderItemReadSerializer(many=True, read_only=True)

    class Meta:
        model  = CustomerOrder
        fields = [
            "id", "order_id", "customer_name", "customer_mobile",
            "subtotal", "advance", "balance", "status",
            "items", "created_at", "updated_at",
        ]


class ShopNotificationSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(source="order.order_id", read_only=True, allow_null=True)

    class Meta:
        model  = ShopNotification
        fields = ["id", "notif_type", "message", "is_read", "order_id", "created_at"]





class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            'id', 'name', 'qty', 'price', 'unit',
            'product', 'is_stock_item',
        ]

class PublicInvoiceSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for public invoice view.
    Returns everything the customer needs to see.
    No sensitive shop owner data included.
    """
    items = InvoiceItemSerializer(
        many=True,
        source='invoice_items',   # ← use your actual related_name
        read_only=True
    )

    class Meta:
        model = Invoice
        fields = [
            'invoice_id',
            'date',
            'customer_name',
            'customer_mobile',
            'customer_gst',
            'shop_name',
            'shop_address',
            'shop_gst',
            'is_gst',
            'subtotal',
            'gst_amt',
            'discount',
            'advance',
            'total',
            'balance',
            'payment',
            'status',
            'items',
        ]



class DashboardStatsSerializer(serializers.Serializer):
    today_sales          = serializers.FloatField()
    today_invoice_count  = serializers.IntegerField()
    today_paid_amount    = serializers.FloatField()
    today_unpaid_amount  = serializers.FloatField()

    week_billing         = serializers.FloatField()
    week_invoice_count   = serializers.IntegerField()
    week_paid_amount     = serializers.FloatField()
    week_unpaid_amount   = serializers.FloatField()

    month_billing        = serializers.FloatField()
    month_invoice_count  = serializers.IntegerField()
    paid_amount          = serializers.FloatField()
    unpaid_amount        = serializers.FloatField()

    total_billing        = serializers.FloatField()
    invoice_count        = serializers.IntegerField()
    customer_count       = serializers.IntegerField()
    stock_items          = serializers.IntegerField()
    stock_value          = serializers.FloatField()
    low_stock_count      = serializers.IntegerField()
    recent_invoices      = serializers.ListField(default=[])