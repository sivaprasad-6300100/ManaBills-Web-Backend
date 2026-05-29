from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import date
from decimal import Decimal
import razorpay
from django.conf import settings
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))



from .models import ShopProfile, Customer, Product, Invoice, InvoiceItem, StockTransaction
from .serializers import (
    ShopProfileSerializer,
    CustomerSerializer,
    ProductSerializer,
    ProductLowStockSerializer,
    ProductStatsSerializer,
    InvoiceReadSerializer,
    InvoiceWriteSerializer,
    MarkPaidSerializer,
    StockTransactionSerializer,
    GstMonthReportSerializer,
    DashboardStatsSerializer,
)

# ── Helper: date string DD/MM/YYYY → date object ──────────────
MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December",
]

def _today_str():
    d = date.today()
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


# ═══════════════════════════════════════════════════════════════
#   1.  SHOP PROFILE
# ═══════════════════════════════════════════════════════════════
class ShopProfileView(APIView):
    """
    GET  /api/business/shop-profile/  → return current user's shop profile
    POST /api/business/shop-profile/  → create or fully update shop profile
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            profile = ShopProfile.objects.get(user=request.user)
            serializer = ShopProfileSerializer(profile)
            return Response(serializer.data)
        except ShopProfile.DoesNotExist:
            return Response(
                {"detail": "Shop profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        """Create if not exists, otherwise update (upsert)"""
        try:
            profile = ShopProfile.objects.get(user=request.user)
            serializer = ShopProfileSerializer(profile, data=request.data, partial=True)
        except ShopProfile.DoesNotExist:
            serializer = ShopProfileSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request):
        try:
            ShopProfile.objects.get(user=request.user).delete()
            return Response({"detail": "Shop profile deleted."}, status=status.HTTP_204_NO_CONTENT)
        except ShopProfile.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


# ═══════════════════════════════════════════════════════════════
#   2.  CUSTOMERS
# ═══════════════════════════════════════════════════════════════
class CustomerListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/business/customers/         → list all customers
    POST /api/business/customers/         → create customer
    """
    serializer_class   = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs     = Customer.objects.filter(user=self.request.user)
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(mobile__icontains=search)
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CustomerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/business/customers/<id>/  → retrieve
    PATCH  /api/business/customers/<id>/  → update
    DELETE /api/business/customers/<id>/  → delete
    """
    serializer_class   = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Customer.objects.filter(user=self.request.user)


# ═══════════════════════════════════════════════════════════════
#   3.  PRODUCTS  (Stock)
# ═══════════════════════════════════════════════════════════════
class ProductListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/business/products/  → list products (with optional ?search= / ?category=)
    POST /api/business/products/  → add product (auto-merges if same name exists)
    """
    serializer_class   = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs       = Product.objects.filter(user=self.request.user, is_active=True)
        search   = self.request.query_params.get("search",   "").strip()
        category = self.request.query_params.get("category", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        if category and category != "All":
            qs = qs.filter(category=category)
        return qs

    def create(self, request, *args, **kwargs):
        """Auto-merge qty if product with same name already exists"""
        name_lower = request.data.get("name", "").strip().lower()
        existing = Product.objects.filter(
            user=request.user,
            name__iexact=name_lower,
            is_active=True,
        ).first()

        if existing:
            # Merge: add qty, update prices
            incoming_qty   = Decimal(str(request.data.get("qty", 0)))
            new_sell_price = request.data.get("selling_price")
            new_buy_price  = request.data.get("purchase_price")

            existing.qty += incoming_qty
            if new_sell_price:
                existing.selling_price = Decimal(str(new_sell_price))
            if new_buy_price:
                existing.purchase_price = Decimal(str(new_buy_price))
            existing.save()

            # Log ENTRY transaction
            StockTransaction.objects.create(
                user    = request.user,
                product = existing,
                tx_type = "ENTRY",
                qty     = incoming_qty,
                note    = "Merged into existing stock",
            )

            return Response(
                {**ProductSerializer(existing).data, "merged": True},
                status=status.HTTP_200_OK
            )

        # New product
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save(user=request.user)

        # Log ENTRY transaction
        StockTransaction.objects.create(
            user    = request.user,
            product = product,
            tx_type = "ENTRY",
            qty     = product.qty,
            note    = "New stock entry",
        )

        return Response(
            {**serializer.data, "merged": False},
            status=status.HTTP_201_CREATED
        )


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/business/products/<id>/  → retrieve
    PATCH  /api/business/products/<id>/  → update
    DELETE /api/business/products/<id>/  → soft-delete (is_active=False)
    """
    serializer_class   = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Soft-delete — keeps transaction history intact"""
        product = self.get_object()
        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])
        return Response(
            {"detail": f'"{product.name}" removed from stock.'},
            status=status.HTTP_204_NO_CONTENT,
        )


class ProductSearchView(APIView):
    """
    GET /api/business/products/search/?q=<query>
    Used by CreateInvoice autocomplete — returns only in-stock items
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response([])

        products = Product.objects.filter(
            user      = request.user,
            is_active = True,
            qty__gt   = 0,
            name__icontains=query,
        ).order_by("name")[:8]

        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


class LowStockView(APIView):
    """
    GET /api/business/products/low-stock/
    Returns all products where qty <= min_qty_alert
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        products = Product.objects.filter(
            user      = request.user,
            is_active = True,
        ).filter(qty__lte=F("min_qty_alert"))

        serializer = ProductLowStockSerializer(products, many=True)
        return Response(serializer.data)


class StockStatsView(APIView):
    """
    GET /api/business/products/stats/
    Returns aggregated stock stats for dashboard
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Product.objects.filter(user=request.user, is_active=True)

        total_items     = qs.count()
        total_qty       = float(qs.aggregate(t=Sum("qty"))["t"] or 0)
        low_stock_count = qs.filter(qty__lte=F("min_qty_alert")).count()

        # total_value = sum(qty * selling_price)
        total_value = sum(
            float(p.qty) * float(p.selling_price)
            for p in qs.only("qty", "selling_price")
        )

        data = {
            "total_items":     total_items,
            "total_qty":       total_qty,
            "total_value":     total_value,
            "low_stock_count": low_stock_count,
        }
        return Response(ProductStatsSerializer(data).data)


# ═══════════════════════════════════════════════════════════════
#   4.  INVOICES
# ═══════════════════════════════════════════════════════════════
class InvoiceListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/business/invoices/   → list invoices
         ?status=Paid/Partial/Pending
         ?payment=Cash/UPI/...
         ?search=<customer name / invoice id / mobile>
    POST /api/business/invoices/   → create invoice (auto-deducts stock)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return InvoiceWriteSerializer
        return InvoiceReadSerializer

    def get_queryset(self):
        qs      = Invoice.objects.filter(user=self.request.user).prefetch_related("items")
        search  = self.request.query_params.get("search",  "").strip()
        st      = self.request.query_params.get("status",  "").strip()
        payment = self.request.query_params.get("payment", "").strip()

        if search:
            qs = qs.filter(
                Q(customer_name__icontains=search)
                | Q(invoice_id__icontains=search)
                | Q(customer_mobile__icontains=search)
            )
        if st and st != "All":
            qs = qs.filter(status=st)
        if payment and payment != "All":
            qs = qs.filter(payment=payment)

        return qs


class InvoiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/business/invoices/<id>/  → retrieve with items
    PATCH  /api/business/invoices/<id>/  → update
    DELETE /api/business/invoices/<id>/  → delete
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return InvoiceWriteSerializer
        return InvoiceReadSerializer

    def get_queryset(self):
        return Invoice.objects.filter(user=self.request.user).prefetch_related("items")


class InvoiceMarkPaidView(APIView):
    """
    PATCH /api/business/invoices/<id>/mark-paid/
    Sets advance = total → status becomes "Paid", balance = 0
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            invoice = Invoice.objects.get(pk=pk, user=request.user)
        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        invoice.advance = invoice.total
        invoice.save()   # save() auto-calculates balance + status

        return Response(InvoiceReadSerializer(invoice).data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════
#   5.  STOCK TRANSACTIONS  (read-only audit log)
# ═══════════════════════════════════════════════════════════════
class StockTransactionListView(generics.ListAPIView):
    """
    GET /api/business/stock-transactions/
    ?product=<id>  → filter by product
    """
    serializer_class   = StockTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs         = StockTransaction.objects.filter(user=self.request.user)
        product_id = self.request.query_params.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs


# ═══════════════════════════════════════════════════════════════
#   6.  GST REPORTS
#       Returns monthly / quarterly breakdown for selected year
# ═══════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def gst_reports(request):
    year = int(request.query_params.get("year", date.today().year))

    # All GST invoices for this year
    gst_invoices = Invoice.objects.filter(
        user=request.user,
        is_gst=True,
        created_at__year=year,
    )

    # All products with ITC
    all_products = Product.objects.filter(
        user=request.user,
        is_active=True,
        purchase_price__gt=0,
        gst_rate__gt=0,
    )

    # Get all GST payment records for this year
    from .models import GstPayment
    gst_payments = {
        p.month: p
        for p in GstPayment.objects.filter(user=request.user, year=year)
    }

    # Helper: get ITC for a product
    def get_itc(product):
        if float(product.purchase_gst) > 0:
            return float(product.purchase_gst)
        return float(product.purchase_price) * float(product.gst_rate) / 100

    # Total ITC from all products (for fallback distribution)
    total_itc = sum(get_itc(p) for p in all_products)

    # Count months that have invoices (for even distribution)
    months_with_invoices = [
        m for m in range(1, 13)
        if gst_invoices.filter(created_at__month=m).exists()
    ]
    active_month_count = len(months_with_invoices) or 1

    monthly_data = []
    for idx, month_name in enumerate(MONTHS):
        month_num      = idx + 1
        month_invoices = gst_invoices.filter(created_at__month=month_num)
        invoice_count  = month_invoices.count()
        taxable_value  = float(month_invoices.aggregate(t=Sum("subtotal"))["t"] or 0)
        gst_collected  = float(month_invoices.aggregate(g=Sum("gst_amt"))["g"] or 0)

        # B2B = customer has GSTIN, B2C = no GSTIN
        b2b_count = month_invoices.exclude(customer_gst="").count()
        b2c_count = month_invoices.filter(customer_gst="").count()

        # ITC: first try products with purchase_date in this month
        dated_itc = sum(
            get_itc(p) for p in all_products.filter(
                purchase_date__year=year,
                purchase_date__month=month_num,
            )
        )

        # Fallback: if no purchase_date set, distribute evenly across invoice months
        if dated_itc == 0 and invoice_count > 0:
            dated_itc = total_itc / active_month_count

        itc_eligible = dated_itc
        itc_claimed  = dated_itc * 0.85
        itc_pending  = dated_itc * 0.15

        # GST Payment status from DB
        payment = gst_payments.get(month_num)
        is_paid    = payment.is_paid    if payment else False
        paid_date  = str(payment.paid_date) if payment and payment.paid_date else None
        due_amount = max(0, gst_collected - itc_claimed)

        monthly_data.append({
            "month":          month_num,
            "invoice_count":  invoice_count,
            "b2b_count":      b2b_count,
            "b2c_count":      b2c_count,
            "taxable_value":  taxable_value,
            "gst_collected":  gst_collected,
            "total_value":    taxable_value + gst_collected,
            "itc_eligible":   itc_eligible,
            "itc_claimed":    itc_claimed,
            "itc_pending":    itc_pending,
            "gst_paid":       is_paid,
            "gst_paid_date":  paid_date,
            "gst_due_amount": 0 if is_paid else due_amount,
        })

    return Response(monthly_data)


# ── Mark GST as Paid ──────────────────────────────────────────
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mark_gst_paid(request):
    """
    POST /api/business/gst-mark-paid/
    Body: { year: 2026, month: 5, paid_amount: 180.00 }
    Saves payment to DB so it persists across sessions.
    """
    from .models import GstPayment
    year        = int(request.data.get("year",  date.today().year))
    month       = int(request.data.get("month", date.today().month))
    paid_amount = float(request.data.get("paid_amount", 0))

    payment, _ = GstPayment.objects.get_or_create(
        user=request.user, year=year, month=month
    )
    payment.is_paid     = True
    payment.paid_date   = date.today()
    payment.paid_amount = paid_amount
    payment.save()

    return Response({
        "success": True,
        "year": year,
        "month": month,
        "paid_date": str(payment.paid_date),
        "paid_amount": paid_amount,
    })

# ═══════════════════════════════════════════════════════════════
#   7.  DASHBOARD STATS (OPTIMIZED)
# ═══════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    """
    GET /api/business/dashboard/
    Returns all 12 KPI numbers — single optimized query with aggregates.
    Replaces 6 separate database round trips with 1 efficient query.
    """
    user = request.user
    today = _today_str()
    now = timezone.now()

    invoices = Invoice.objects.filter(user=user)

    # Single aggregation query — all metrics at once
    agg = invoices.aggregate(
        # Today
        today_sales=Sum("total", filter=Q(date=today)),
        today_count=Count("id", filter=Q(date=today)),

        # This month
        month_billing=Sum("total", filter=Q(
            created_at__month=now.month,
            created_at__year=now.year
        )),
        month_count=Count("id", filter=Q(
            created_at__month=now.month,
            created_at__year=now.year
        )),

        # All-time
        total_billing=Sum("total"),
        invoice_count=Count("id"),

        # Paid / Unpaid
        paid_amount=Sum("advance", filter=Q(status="Paid")),
        unpaid_amount=Sum("balance", filter=Q(status__in=["Pending", "Partial"])),
    )

    # Stock stats (2nd query — unavoidable for complex stock value calc)
    products = Product.objects.filter(user=user, is_active=True)
    stock_items = products.count()
    low_stock_count = products.filter(qty__lte=F("min_qty_alert")).count()
    stock_value = sum(
        float(p.qty) * float(p.selling_price)
        for p in products.only("qty", "selling_price")
    )

    data = {
        "today_sales":          float(agg["today_sales"] or 0),
        "today_invoice_count":  int(agg["today_count"] or 0),
        "unpaid_amount":        float(agg["unpaid_amount"] or 0),
        "paid_amount":          float(agg["paid_amount"] or 0),
        "month_billing":        float(agg["month_billing"] or 0),
        "month_invoice_count":  int(agg["month_count"] or 0),
        "total_billing":        float(agg["total_billing"] or 0),
        "invoice_count":        int(agg["invoice_count"] or 0),
        "customer_count":       Customer.objects.filter(user=user).count(),
        "stock_items":          stock_items,
        "stock_value":          stock_value,
        "low_stock_count":      low_stock_count,
    }

    return Response(DashboardStatsSerializer(data).data)

# ---------------------------------------------------
# --------------------------------
# ---------------------

"""
Add these views to business_billing/views.py
"""
# from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from .models import ShopScanner, ShopProfile, Product, CustomerOrder, CustomerOrderItem, ShopNotification
from .serializers import (
    ShopScannerSerializer, PublicShopSerializer,
    PublicProductSerializer, CustomerOrderWriteSerializer,
    CustomerOrderReadSerializer, ShopNotificationSerializer,
)


# ─── 1. Auto-create scanner when shop profile is saved ───────────
# Add this signal to business_billing/signals.py

# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from .models import ShopProfile, ShopScanner
#
# @receiver(post_save, sender=ShopProfile)
# def create_shop_scanner(sender, instance, created, **kwargs):
#     if created:
#         ShopScanner.objects.get_or_create(user=instance.user)


# ─── 2. Get scanner info for owner dashboard ─────────────────────

class ShopScannerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Only create scanner if shop profile exists
        try:
            profile = ShopProfile.objects.get(user=request.user)
        except ShopProfile.DoesNotExist:
            return Response(
                {"detail": "Please create your shop profile first."},
                status=status.HTTP_404_NOT_FOUND
            )

        phone = getattr(request.user, 'mobile_number', '') or str(request.user.pk)
        scanner, _ = ShopScanner.objects.get_or_create(
            user=request.user,
            defaults={"scanner_id": f"mb-{phone}-001", "is_active": True}
        )
        if not scanner.scanner_id:
            scanner.scanner_id = f"mb-{phone}-001"
            scanner.save(update_fields=["scanner_id"])

        return Response(ShopScannerSerializer(scanner, context={"request": request}).data)

    def patch(self, request):
        scanner = get_object_or_404(ShopScanner, user=request.user)
        scanner.is_active = request.data.get("is_active", scanner.is_active)
        scanner.save()
        return Response(ShopScannerSerializer(scanner, context={"request": request}).data)

# ─── 3. PUBLIC — Customer scans QR, gets shop info + products ────
class PublicShopView(APIView):
    """
    GET /api/public/shop/<scanner_id>/
    No authentication required — called from customer's phone after QR scan
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, scanner_id):
        scanner = get_object_or_404(ShopScanner, scanner_id=scanner_id, is_active=True)
        scanner.scan_count += 1
        scanner.save(update_fields=["scan_count"])

        profile = get_object_or_404(ShopProfile, user=scanner.user)
        products = Product.objects.filter(user=scanner.user, is_active=True, qty__gt=0).order_by("name")

        return Response({
            "shop": PublicShopSerializer(profile).data,
            "products": PublicProductSerializer(products, many=True).data,
            "scanner_id": str(scanner_id),
        })


# ─── 4. PUBLIC — Customer places order ───────────────────────────
class PlaceOrderView(APIView):
    """
    POST /api/public/shop/<scanner_id>/order/
    No authentication required.
    Body: { customer_name, customer_mobile, items: [{product_id, qty}], advance }
    """
    permission_classes = [permissions.AllowAny]

    @db_transaction.atomic
    def post(self, request, scanner_id):
        scanner = get_object_or_404(ShopScanner, scanner_id=scanner_id, is_active=True)

        serializer = CustomerOrderWriteSerializer(
            data=request.data,
            context={"scanner": scanner}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Notify shop owner
        ShopNotification.objects.create(
            user       = scanner.user,
            order      = order,
            notif_type = "new_order",
            message    = f"New order {order.order_id} from {order.customer_name} — ₹{order.subtotal}",
        )

        return Response(CustomerOrderReadSerializer(order).data, status=status.HTTP_201_CREATED)


# ─── 5. OWNER — List & manage customer orders ────────────────────
class CustomerOrderListView(generics.ListAPIView):
    """GET /api/business/orders/  — owner sees all customer orders"""
    serializer_class   = CustomerOrderReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs     = CustomerOrder.objects.filter(user=self.request.user).prefetch_related("items")
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs


class CustomerOrderDetailView(APIView):
    """PATCH /api/business/orders/<id>/  — update order status"""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        order = get_object_or_404(CustomerOrder, pk=pk, user=request.user)
        new_status = request.data.get("status")

        VALID_TRANSITIONS = {
            "new":       ["packing", "cancelled"],
            "packing":   ["ready", "cancelled"],
            "ready":     ["completed"],
            "completed": [],
            "cancelled": [],
        }

        if new_status not in VALID_TRANSITIONS.get(order.status, []):
            return Response(
                {"error": f"Cannot move from '{order.status}' to '{new_status}'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        # Notify customer (via WhatsApp / SMS in real implementation)
        if new_status == "ready":
            ShopNotification.objects.create(
                user       = request.user,
                order      = order,
                notif_type = "ready",
                message    = f"Order {order.order_id} is ready for pickup. Balance: ₹{order.balance}",
            )

        # Auto-generate invoice when completed
        if new_status == "completed":
            _create_invoice_from_order(order)

        return Response(CustomerOrderReadSerializer(order).data)


def _create_invoice_from_order(order):
    """Helper: convert completed order → Invoice"""
    from .models import Invoice, InvoiceItem, StockTransaction
    from decimal import Decimal

    invoice = Invoice.objects.create(
        user            = order.user,
        invoice_id      = f"INV-{order.order_id[4:]}",
        customer_name   = order.customer_name,
        customer_mobile = order.customer_mobile,
        subtotal        = order.subtotal,
        advance         = order.advance,
        total           = order.subtotal,
        is_gst          = False,
        payment         = "Mixed",
        date            = order.created_at.strftime("%d/%m/%Y"),
    )

    for item in order.items.all():
        InvoiceItem.objects.create(
            invoice      = invoice,
            product      = item.product,
            name         = item.name,
            qty          = item.qty,
            price        = item.price,
            unit         = item.unit,
            is_stock_item= item.product is not None,
        )

    order.invoice = invoice
    order.save(update_fields=["invoice"])
    return invoice


# ─── 6. OWNER — Notifications ────────────────────────────────────
class NotificationsView(APIView):
    """
    GET   /api/business/notifications/      → list
    PATCH /api/business/notifications/      → mark all read
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifs = ShopNotification.objects.filter(user=request.user)[:50]
        return Response(ShopNotificationSerializer(notifs, many=True).data)

    def patch(self, request):
        ShopNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"detail": "All notifications marked as read"})


class NotificationDetailView(APIView):
    """PATCH /api/business/notifications/<id>/read/ — mark single as read"""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        notif = get_object_or_404(ShopNotification, pk=pk, user=request.user)
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response({"detail": "Marked as read"})



class PublicOrdersByMobileView(APIView):
    """
    GET /api/public/shop/<scanner_id>/orders/?mobile=9999999999
    No authentication — customers check their own orders by mobile number.
    Only returns orders placed through this specific scanner.
    """
    permission_classes = [permissions.AllowAny]
 
    def get(self, request, scanner_id):
        # Try to find scanner, auto-create if missing
        mobile = request.query_params.get("mobile", "").strip()
 
        if not mobile or len(mobile) != 10 or not mobile.isdigit():
            return Response(
                {"detail": "Provide a valid 10-digit mobile number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        scanner = get_object_or_404(ShopScanner, scanner_id=scanner_id, is_active=True)
 
        orders = CustomerOrder.objects.filter(
            scanner         = scanner,
            customer_mobile = mobile,
        ).prefetch_related("items").order_by("-created_at")[:20]
 
        return Response(CustomerOrderReadSerializer(orders, many=True).data)


# =================================================

#            Razorpay integrations for public orders

# ======================================================

@csrf_exempt
def create_razorpay_order(request , scanner_id=None):
    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    data = json.loads(request.body)
    amount = int(float(data['amount']) * 100)  # convert to paise
    
    order = client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })
    
    return JsonResponse({
        "razorpay_order_id": order['id'],
        "amount": order['amount'],
        "currency": order['currency']
    })




@csrf_exempt
def verify_payment(request, scanner_id=None):
    try:
        data = json.loads(request.body)
        client.utility.verify_payment_signature({
            'razorpay_order_id':   data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature':  data['razorpay_signature'],
        })
        return JsonResponse({"status": "verified"})
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({"status": "failed"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "detail": str(e)}, status=400)




