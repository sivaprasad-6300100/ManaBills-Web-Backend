from django.urls import path
from . import views

app_name = "business_billing"

urlpatterns = [

    # ── Shop Profile ────────────────────────────────────────────
    # GET / POST / DELETE
    path("shop-profile/", views.ShopProfileView.as_view(), name="shop-profile"),

    # ── Customers ───────────────────────────────────────────────
    # GET  (list + ?search=) / POST (create)
    path("customers/",       views.CustomerListCreateView.as_view(), name="customer-list"),
    # GET / PATCH / DELETE  (single customer)
    path("customers/<int:pk>/", views.CustomerDetailView.as_view(),  name="customer-detail"),

    # ── Products / Stock ────────────────────────────────────────
    # GET (list + ?search= + ?category=) / POST (add/merge stock)
    path("products/",             views.ProductListCreateView.as_view(), name="product-list"),
    # GET / PATCH / DELETE (soft)
    path("products/<int:pk>/",    views.ProductDetailView.as_view(),     name="product-detail"),

    # GET ?q=<query>  → autocomplete for invoice
    path("products/search/",      views.ProductSearchView.as_view(),     name="product-search"),
    # GET  → products where qty <= min_qty_alert
    path("products/low-stock/",   views.LowStockView.as_view(),          name="product-low-stock"),
    # GET  → aggregated stock stats
    path("products/stats/",       views.StockStatsView.as_view(),        name="product-stats"),

    # ── Invoices ────────────────────────────────────────────────
    # GET (list + filters) / POST (create + auto stock deduct)
    path("invoices/",             views.InvoiceListCreateView.as_view(), name="invoice-list"),
    # GET / PATCH / DELETE
    path("invoices/<int:pk>/",    views.InvoiceDetailView.as_view(),     name="invoice-detail"),
    # PATCH → marks invoice as fully paid
    path("invoices/<int:pk>/mark-paid/", views.InvoiceMarkPaidView.as_view(), name="invoice-mark-paid"),

    # ── Stock Transactions (audit log) ──────────────────────────
    # GET (list + ?product=<id>)
    path("stock-transactions/",   views.StockTransactionListView.as_view(), name="stock-transactions"),

    # ── GST Reports ─────────────────────────────────────────────
    # GET ?year=2025 &view=monthly|quarterly
    path("gst-reports/",          views.gst_reports,                    name="gst-reports"),

    # ── Dashboard Stats ─────────────────────────────────────────
    # GET → all KPIs for BusinessHome.jsx
    path("dashboard/",            views.dashboard_stats,                name="dashboard-stats"),
]