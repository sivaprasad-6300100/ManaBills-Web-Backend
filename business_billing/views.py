from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import date
from decimal import Decimal

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
# ═══════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def gst_reports(request):
    """
    GET /api/business/gst-reports/?year=2025&view=monthly
    view = "monthly" (default) | "quarterly"
    """
    year = int(request.query_params.get("year", date.today().year))
    view = request.query_params.get("view", "monthly")

    # All GST invoices for this user in the selected year
    gst_invoices = Invoice.objects.filter(
        user   = request.user,
        is_gst = True,
        created_at__year = year,
    )

    # Build monthly data
    monthly_data = []
    for idx, month_name in enumerate(MONTHS):
        month_invoices = gst_invoices.filter(created_at__month=idx + 1)
        taxable_value  = float(month_invoices.aggregate(t=Sum("subtotal"))["t"] or 0)
        gst_collected  = float(month_invoices.aggregate(g=Sum("gst_amt"))["g"] or 0)

        monthly_data.append({
            "month":         month_name,
            "invoice_count": month_invoices.count(),
            "taxable_value": taxable_value,
            "gst_collected": gst_collected,
            "total_value":   taxable_value + gst_collected,
        })

    if view == "quarterly":
        QUARTERS = [
            {"label": "Q1 (Apr–Jun)", "months": [3, 4, 5]},
            {"label": "Q2 (Jul–Sep)", "months": [6, 7, 8]},
            {"label": "Q3 (Oct–Dec)", "months": [9, 10, 11]},
            {"label": "Q4 (Jan–Mar)", "months": [0, 1, 2]},
        ]
        result = []
        for q in QUARTERS:
            rows = [monthly_data[m] for m in q["months"]]
            result.append({
                "month":         q["label"],
                "invoice_count": sum(r["invoice_count"] for r in rows),
                "taxable_value": sum(r["taxable_value"] for r in rows),
                "gst_collected": sum(r["gst_collected"] for r in rows),
                "total_value":   sum(r["total_value"]   for r in rows),
            })
        return Response(GstMonthReportSerializer(result, many=True).data)

    return Response(GstMonthReportSerializer(monthly_data, many=True).data)


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