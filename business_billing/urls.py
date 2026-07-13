from django.urls import path
from . import views
from .views import PublicShopView, PlaceOrderView, PublicOrdersByMobileView,ShopLogoUploadView,ProductImageUploadView




urlpatterns = [

    path("shop-profile/",           views.ShopProfileView.as_view()),
    path("scanner/",                views.ShopScannerView.as_view()),
    path("customers/",              views.CustomerListCreateView.as_view()),
    path("customers/<int:pk>/",     views.CustomerDetailView.as_view()),
    path("products/",               views.ProductListCreateView.as_view()),
    path("products/<int:pk>/",      views.ProductDetailView.as_view()),
    path("products/search/",        views.ProductSearchView.as_view()),
    path("products/low-stock/",     views.LowStockView.as_view()),
    path("products/stats/",         views.StockStatsView.as_view()),
    path("invoices/",               views.InvoiceListCreateView.as_view()),
    path("invoices/<int:pk>/",      views.InvoiceDetailView.as_view()),
    path("invoices/<int:pk>/mark-paid/", views.InvoiceMarkPaidView.as_view()),
    path("stock-transactions/",     views.StockTransactionListView.as_view()),
    path("gst-reports/",            views.gst_reports),
    path("gst-mark-paid/", views.mark_gst_paid),
    path("dashboard/",              views.dashboard_stats),     
    path("orders/",                 views.CustomerOrderListView.as_view()),      
    path("orders/<int:pk>/",        views.CustomerOrderDetailView.as_view()),    
    path("notifications/",          views.NotificationsView.as_view()),          
    path("notifications/<int:pk>/read/", views.NotificationDetailView.as_view()),
    path("create-razorpay-order/",  views.create_razorpay_order),
    path("verify-payment/",         views.verify_payment),
    # path("scan-invoice/", views.ScanInvoiceView.as_view()),

#  Public Api's for mobile app and QR code scanning 
    path("shop/<str:scanner_id>/",                    views.PublicShopView.as_view()),
    path("shop/<str:scanner_id>/order/",              views.PlaceOrderView.as_view()),
    path("shop/<str:scanner_id>/orders/",             views.PublicOrdersByMobileView.as_view()),
    path("shop/<str:scanner_id>/create-razorpay-order/", views.create_razorpay_order),
    path("shop/<str:scanner_id>/verify-payment/",    views.verify_payment),

    path("shop/<str:scanner_id>/send-otp/",            views.SendCustomerOtpView.as_view()),
    path("shop/<str:scanner_id>/verify-otp/",           views.VerifyCustomerOtpView.as_view()),
    path("shop/<str:scanner_id>/save-customer-name/",   views.SaveCustomerNameView.as_view()),


    
    path('itc-opening-balance/', views.itc_opening_balance),
    
    # Add these 2 lines inside urlpatterns:
    path(
        'invoices/public/<str:invoice_id>/',
        views.public_invoice_view,
        name='public-invoice'
    ),

    # invoices numbers generate url 
    path('invoices/next-id/', views.NextInvoiceIdView.as_view()),

    # path("register-device/",         RegisterDeviceView.as_view()),
    # path("devices/",                  DeviceListView.as_view()),
    # path("devices/<str:device_id>/",  DeviceListView.as_view()),

    path("chart-stats/", views.chart_stats, name="chart-stats"),
     path("shop-profile/logo/", ShopLogoUploadView.as_view(), name="shop-logo-upload"),
     path("products/<int:pk>/image/", ProductImageUploadView.as_view(), name="product-image-upload"),
]


