from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.postgres.indexes import GinIndex
from accounts.models import User


# ═══════════════════════════════════════════════════════════════
#   1.  SHOP PROFILE
#       One shop profile per user — holds business identity,
#       GST settings, and shop type (Kirana, Medical, etc.)
# ═══════════════════════════════════════════════════════════════
class ShopProfile(models.Model):

    SHOP_TYPE_CHOICES = [
        ("Kirana Store",    "Kirana Store"),
        ("Clothing",        "Clothing"),
        ("HardWare",        "HardWare"),
        ("Medical",         "Medical"),
        ("Gold and Silver", "Gold and Silver"),
        ("Resturants",      "Resturants"),
        ("Genral Store",    "Genral Store"),
        ("Others",          "Others"),
    ]

    user         = models.OneToOneField(
                       User, on_delete=models.CASCADE,
                       related_name="shop_profile"
                   )
    shop_name    = models.CharField(max_length=255)
    owner_name   = models.CharField(max_length=255)
    mobile       = models.CharField(max_length=15)
    extra_mobile = models.CharField(max_length=15, blank=True, default="")
    address      = models.TextField()
    shop_type    = models.CharField(
                       max_length=30, choices=SHOP_TYPE_CHOICES,
                       blank=True, default=""
                   )
    timings      = models.CharField(max_length=100, blank=True, default="")

    # GST
    gst_enabled  = models.BooleanField(default=False)
    gst_number   = models.CharField(max_length=15, blank=True, default="")

    # Logo — store as URL / path (frontend sends object URL; store as text)
    logo_url     = models.TextField(blank=True, default="")

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Shop Profile"
        verbose_name_plural = "Shop Profiles"
        indexes = [
            models.Index(fields=["user", "gst_enabled"], name="shopprofile_user_gst_idx"),
        ]

    def __str__(self):
        return f"{self.shop_name} — {self.user.mobile_number}"


# ═══════════════════════════════════════════════════════════════
#   2.  CUSTOMER
# ═══════════════════════════════════════════════════════════════
class Customer(models.Model):

    user       = models.ForeignKey(
                     User, on_delete=models.CASCADE,
                     related_name="bb_customers"
                 )
    name       = models.CharField(max_length=255)
    mobile     = models.CharField(max_length=15, blank=True, default="")
    email      = models.EmailField(blank=True, default="")
    gst_number = models.CharField(max_length=15, blank=True, default="")
    address    = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Customer"
        verbose_name_plural = "Customers"
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["user"], name="customer_user_idx"),
            models.Index(fields=["user", "mobile"], name="customer_user_mobile_idx"),
            # Trigram index for fuzzy search — requires pg_trgm extension
            GinIndex(fields=["name"], name="customer_name_gin", 
                     opclasses=["gin_trgm_ops"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.mobile})"


# ═══════════════════════════════════════════════════════════════
#   3.  PRODUCT  (Stock Item)
#       Supports all shop types with optional extra fields.
#       Kirana / Restaurant / General → base fields only
#       Clothing / HardWare / Medical / Gold → extra fields
# ═══════════════════════════════════════════════════════════════
class Product(models.Model):

    UNIT_CHOICES = [
        ("piece",   "Piece"),
        ("kg",      "KG"),
        ("gram",    "Gram"),
        ("litre",   "Litre"),
        ("ml",      "ML"),
        ("bag",     "Bag"),
        ("box",     "Box"),
        ("dozen",   "Dozen"),
        ("metre",   "Metre"),
        ("set",     "Set"),
        ("roll",    "Roll"),
        ("bundle",  "Bundle"),
        ("packet",  "Packet"),
        ("strip",   "Strip"),
        ("bottle",  "Bottle"),
        ("pair",    "Pair"),
        ("sachet",  "Sachet"),
        ("vial",    "Vial"),
    ]

    # ── Core ──────────────────────────────────────────────────
    user           = models.ForeignKey(
                         User, on_delete=models.CASCADE,
                         related_name="bb_products"
                     )
    name           = models.CharField(max_length=255)
    category       = models.CharField(max_length=100, blank=True, default="General")
    unit           = models.CharField(max_length=20, choices=UNIT_CHOICES, default="piece")
    purchase_price = models.DecimalField(
                         max_digits=12, decimal_places=2, default=0,
                         validators=[MinValueValidator(0)]
                     )
    selling_price  = models.DecimalField(
                         max_digits=12, decimal_places=2, default=0,
                         validators=[MinValueValidator(0)]
                     )
    qty            = models.DecimalField(
                         max_digits=12, decimal_places=2, default=0,
                         validators=[MinValueValidator(0)]
                     )
    min_qty_alert  = models.DecimalField(
                         max_digits=10, decimal_places=2, default=5,
                         validators=[MinValueValidator(0)]
                     )
    hsn_code       = models.CharField(max_length=20, blank=True, default="")
    shop_type      = models.CharField(max_length=30, blank=True, default="")

    # ── Clothing extras ───────────────────────────────────────
    clothing_type   = models.CharField(max_length=50, blank=True, default="")
    clothing_size   = models.CharField(max_length=20, blank=True, default="")
    clothing_color  = models.CharField(max_length=30, blank=True, default="")
    clothing_gender = models.CharField(max_length=20, blank=True, default="")

    # ── Hardware extras ───────────────────────────────────────
    hw_brand    = models.CharField(max_length=50,  blank=True, default="")
    hw_material = models.CharField(max_length=50,  blank=True, default="")
    hw_model    = models.CharField(max_length=100, blank=True, default="")

    # ── Medical extras ────────────────────────────────────────
    med_company  = models.CharField(max_length=100, blank=True, default="")
    med_schedule = models.CharField(max_length=20,  blank=True, default="OTC")
    med_expiry   = models.CharField(max_length=7,   blank=True, default="")   # "YYYY-MM"
    med_batch    = models.CharField(max_length=50,  blank=True, default="")

    # ── Gold / Silver extras ──────────────────────────────────
    gold_purity    = models.CharField(max_length=20, blank=True, default="")
    metal_type     = models.CharField(max_length=20, blank=True, default="")
    gold_weight    = models.CharField(max_length=20, blank=True, default="")
    making_charges = models.DecimalField(
                         max_digits=10, decimal_places=2, default=0,
                         validators=[MinValueValidator(0)]
                     )

    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Product"
        verbose_name_plural = "Products"
        ordering            = ["name"]
        indexes = [
            # Active products lookup
            models.Index(fields=["user", "is_active"], name="product_user_active_idx"),
            # Category filter (partial — only active)
            models.Index(fields=["user", "category"], name="product_user_cat_idx",
                         condition=models.Q(is_active=True)),
            # Low stock alert dashboard
            models.Index(fields=["user", "qty", "min_qty_alert"], 
                         name="product_low_stock_idx",
                         condition=models.Q(is_active=True)),
            # Medical expiry tracking
            models.Index(fields=["user", "med_expiry"], name="product_med_expiry_idx",
                         condition=models.Q(med_expiry__gt="")),
            # Trigram index for autocomplete search — < 10ms
            GinIndex(fields=["name"], name="product_name_gin",
                     opclasses=["gin_trgm_ops"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(qty__gte=0),
                                   name="product_qty_non_negative"),
            models.CheckConstraint(condition=models.Q(selling_price__gte=0),
                                   name="product_selling_price_non_negative"),
            models.CheckConstraint(condition=models.Q(purchase_price__gte=0),
                                   name="product_purchase_price_non_negative"),
        ]

    def __str__(self):
        return f"{self.name} | qty={self.qty} {self.unit}"

    @property
    def is_low_stock(self):
        return self.qty <= self.min_qty_alert

    @property
    def stock_value(self):
        """Total stock value at selling price"""
        return float(self.qty) * float(self.selling_price)


# ═══════════════════════════════════════════════════════════════
#   4.  INVOICE
# ═══════════════════════════════════════════════════════════════
class Invoice(models.Model):

    STATUS_CHOICES = [
        ("Paid",    "Paid"),
        ("Partial", "Partial"),
        ("Pending", "Pending"),
    ]

    PAYMENT_CHOICES = [
        ("Cash",      "Cash"),
        ("UPI",       "UPI"),
        ("PhonePe",   "PhonePe"),
        ("GooglePay", "GooglePay"),
        ("Card",      "Card"),
        ("Cheque",    "Cheque"),
        ("Credit",    "Credit"),
    ]

    # ── Identity ──────────────────────────────────────────────
    user       = models.ForeignKey(
                     User, on_delete=models.CASCADE,
                     related_name="bb_invoices"
                 )
    invoice_id = models.CharField(max_length=30, unique=True)   # INV-YYMMDD-XXXX

    # ── Customer snapshot ─────────────────────────────────────
    customer        = models.ForeignKey(
                          Customer, on_delete=models.SET_NULL,
                          blank=True, null=True, related_name="invoices"
                      )
    customer_name   = models.CharField(max_length=255)
    customer_mobile = models.CharField(max_length=15, blank=True, default="")
    customer_gst    = models.CharField(max_length=15, blank=True, default="")

    # ── Shop snapshot (captured at invoice time) ───────────────
    shop_name    = models.CharField(max_length=255, blank=True, default="")
    shop_address = models.TextField(blank=True, default="")
    shop_gst     = models.CharField(max_length=15, blank=True, default="")

    # ── Amounts ───────────────────────────────────────────────
    subtotal  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_amt   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance   = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── GST ───────────────────────────────────────────────────
    is_gst    = models.BooleanField(default=False)

    # ── Payment ───────────────────────────────────────────────
    payment   = models.CharField(
                    max_length=20, choices=PAYMENT_CHOICES, default="Cash"
                )
    status    = models.CharField(
                    max_length=10, choices=STATUS_CHOICES, default="Pending"
                )

    # ── Date (DD/MM/YYYY stored as text to match frontend) ────
    date       = models.CharField(max_length=10)       # DD/MM/YYYY
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Invoice"
        verbose_name_plural = "Invoices"
        ordering            = ["-created_at"]
        indexes = [
            # Primary: all invoices for a user, sorted newest first
            models.Index(fields=["user", "-created_at"], name="invoice_user_created_idx"),
            # Status filter (Paid / Pending / Partial tabs)
            models.Index(fields=["user", "status"], name="invoice_user_status_idx"),
            # Payment method filter
            models.Index(fields=["user", "payment"], name="invoice_user_payment_idx"),
            # Customer search
            models.Index(fields=["user", "customer_mobile"], name="invoice_cust_mobile_idx"),
            # GST report
            models.Index(fields=["user", "is_gst", "-created_at"], name="invoice_gst_report_idx"),
            # Pending balance dashboard (partial index)
            models.Index(fields=["user", "balance"], name="invoice_balance_idx",
                         condition=models.Q(balance__gt=0)),
            # Trigram index for customer name search
            GinIndex(fields=["customer_name"], name="invoice_custname_gin",
                     opclasses=["gin_trgm_ops"]),
        ]

    def __str__(self):
        return f"{self.invoice_id} — {self.customer_name} — ₹{self.total}"

    def save(self, *args, **kwargs):
        # Auto-calculate balance and status before save
        self.balance = self.total - self.advance
        if self.advance >= self.total:
            self.status = "Paid"
        elif self.advance > 0:
            self.status = "Partial"
        else:
            self.status = "Pending"
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════
#   5.  INVOICE ITEM  (line items)
# ═══════════════════════════════════════════════════════════════
class InvoiceItem(models.Model):

    invoice    = models.ForeignKey(
                     Invoice, on_delete=models.CASCADE,
                     related_name="items"
                 )
    product    = models.ForeignKey(
                     Product, on_delete=models.SET_NULL,
                     blank=True, null=True, related_name="invoice_items"
                 )

    # Snapshot of product at invoice time
    name       = models.CharField(max_length=255)
    qty        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit       = models.CharField(max_length=20, default="piece")
    amount     = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Stock flag — True if this item was linked to a stock product
    is_stock_item = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Invoice Item"
        verbose_name_plural = "Invoice Items"
        ordering            = ["created_at"]
        indexes = [
            models.Index(fields=["invoice"], name="invoiceitem_invoice_idx"),
            # Stock deduction audit trail (partial)
            models.Index(fields=["product"], name="invoiceitem_product_idx",
                         condition=models.Q(is_stock_item=True)),
        ]

    def __str__(self):
        return f"{self.name} x {self.qty} — ₹{self.amount}"

    def save(self, *args, **kwargs):
        self.amount = self.qty * self.price
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════
#   6.  STOCK TRANSACTION  (audit log for stock movements)
# ═══════════════════════════════════════════════════════════════
class StockTransaction(models.Model):

    TX_TYPE_CHOICES = [
        ("ENTRY",      "Stock Entry"),
        ("DEDUCTION",  "Sale Deduction"),
        ("ADJUSTMENT", "Manual Adjustment"),
    ]

    user          = models.ForeignKey(
                        User, on_delete=models.CASCADE,
                        related_name="bb_stock_transactions"
                    )
    product       = models.ForeignKey(
                        Product, on_delete=models.CASCADE,
                        related_name="stock_transactions"
                    )
    invoice       = models.ForeignKey(
                        Invoice, on_delete=models.SET_NULL,
                        blank=True, null=True, related_name="stock_transactions"
                    )
    tx_type       = models.CharField(max_length=15, choices=TX_TYPE_CHOICES)
    qty           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    note          = models.CharField(max_length=255, blank=True, default="")

    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Stock Transaction"
        verbose_name_plural = "Stock Transactions"
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "-created_at"], name="stocktx_product_created_idx"),
            models.Index(fields=["user", "-created_at"], name="stocktx_user_created_idx"),
        ]

    def __str__(self):
        return f"{self.tx_type} | {self.product.name} | qty={self.qty}"