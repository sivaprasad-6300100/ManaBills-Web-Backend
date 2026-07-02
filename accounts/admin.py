from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.db.models import Sum, Count, Max, Q
from datetime import timedelta
from django.utils.safestring import mark_safe
from .models import User, OtpSession
from subscriptions.models import Subscription
from business_billing.models import Invoice, StockTransaction, CustomerOrder, Product, UserDeviceSession


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('mobile_number', 'full_name', 'plan_badge', 'churn_badge',
                     'invoice_count_30d', 'ltv', 'date_joined')
    readonly_fields = ('activity_summary', 'date_joined')
    fieldsets = (
        (None, {'fields': ('mobile_number', 'password')}),
        ('Personal Info', {'fields': ('full_name',)}),
        ('Full Activity Overview', {'fields': ('activity_summary',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Dates', {'fields': ('date_joined',)}),
    )

    def get_queryset(self, request):
        now = timezone.now()
        qs = super().get_queryset(request)
        return qs.annotate(
            ltv_amount=Sum('subscriptions__amount_paid'),
            invoices_30d=Count('bb_invoices', filter=Q(
                bb_invoices__created_at__gte=now - timedelta(days=30))),
            last_invoice_date=Max('bb_invoices__created_at'),
        )

    def ltv(self, obj):
        return f"₹{obj.ltv_amount or 0:,.0f}"
    ltv.short_description = "LTV"
    ltv.admin_order_field = 'ltv_amount'

    def invoice_count_30d(self, obj):
        return obj.invoices_30d
    invoice_count_30d.short_description = "Invoices (30d)"
    invoice_count_30d.admin_order_field = 'invoices_30d'

    def plan_badge(self, obj):
        sub = obj.subscriptions.filter(status='active').first()
        if not sub:
            return mark_safe('<span style="color:#999;">No plan</span>')
        color = 'green' if sub.days_left > 3 else 'orange' if sub.days_left > 0 else 'red'
        return format_html('<b style="color:{};">{}</b> — {}d left',
                            color, sub.plan_key or sub.module, sub.days_left)
    plan_badge.short_description = "Plan"

    def churn_badge(self, obj):
        """High-value signal: expiring soon + gone quiet = call them now."""
        sub = obj.subscriptions.filter(status='active').first()
        last_inv = obj.last_invoice_date
        if not sub:
            return mark_safe('<span style="color:#999;">—</span>')
        days_since_active = (timezone.now() - last_inv).days if last_inv else 999
        if sub.days_left <= 3 and days_since_active > 7:
            return mark_safe('<b style="color:red;">⚠ HIGH RISK</b>')
        elif sub.days_left <= 7:
            return mark_safe('<span style="color:orange;">Watch</span>')
        return mark_safe('<span style="color:green;">Healthy</span>')
    churn_badge.short_description = "Churn Risk"

    def activity_summary(self, obj):
        now = timezone.now()
        invoices = Invoice.objects.filter(user=obj)
        stock_tx = StockTransaction.objects.filter(user=obj)
        devices = obj.device_sessions.filter(is_active=True)
        orders = CustomerOrder.objects.filter(user=obj)
        products = Product.objects.filter(user=obj, is_active=True)

        agg = invoices.aggregate(
            total_revenue=Sum('total'),
            pending_balance=Sum('balance', filter=Q(balance__gt=0)),
            last_invoice=Max('created_at'),
            gst_invoice_count=Count('id', filter=Q(is_gst=True)),
        )
        inv_30d = invoices.filter(created_at__gte=now - timedelta(days=30)).count()
        inv_prev_30d = invoices.filter(
            created_at__gte=now - timedelta(days=60),
            created_at__lt=now - timedelta(days=30)
        ).count()
        trend = "↑" if inv_30d > inv_prev_30d else "↓" if inv_30d < inv_prev_30d else "→"

        all_subs = obj.subscriptions.all()
        ltv = all_subs.aggregate(t=Sum('amount_paid'))['t'] or 0
        active_sub = all_subs.filter(status='active').first()
        renewal_count = all_subs.filter(module=active_sub.module).count() - 1 if active_sub else 0
        ever_paid = all_subs.exclude(duration='FREE_TRIAL').filter(amount_paid__gt=0).exists()

        failed_otps_7d = OtpSession.objects.filter(
            mobile_number=obj.mobile_number, is_verified=False,
            created_at__gte=now - timedelta(days=7)
        ).count()

        last_active = agg['last_invoice']
        days_dormant = (now - last_active).days if last_active else None
        churn_flag = (active_sub and active_sub.days_left <= 3 and
                      (days_dormant is None or days_dormant > 7))

        low_stock_count = sum(1 for p in products if p.is_low_stock)

        rows = [
            ("Lifetime Value", f"₹{ltv:,.2f}"),
            ("Ever Converted to Paid", "Yes" if ever_paid else "No — trial only"),
            ("Current Plan", f"{active_sub.plan_key if active_sub else '—'} ({active_sub.status if active_sub else 'None'})"),
            ("Expires In", f"{active_sub.days_left} days" if active_sub else "—"),
            ("Renewal Count", str(max(renewal_count, 0))),
            ("Churn Risk", "⚠ HIGH — expiring + dormant" if churn_flag else "Healthy"),
            ("Total Revenue Processed", f"₹{agg['total_revenue'] or 0:,.2f}"),
            ("Pending Customer Balance", f"₹{agg['pending_balance'] or 0:,.2f}"),
            ("Invoices (last 30d)", f"{inv_30d} {trend} (prev 30d: {inv_prev_30d})"),
            ("Last Active (invoice)", last_active.strftime('%d %b %Y, %I:%M %p') if last_active else "Never"),
            ("Days Dormant", str(days_dormant) if days_dormant is not None else "—"),
            ("GST Invoices Used", f"{agg['gst_invoice_count']} of {invoices.count()}"),
            ("Active Products", str(products.count())),
            ("Low Stock Alerts", str(low_stock_count)),
            ("Stock Transactions", str(stock_tx.count())),
            ("Customer Orders (QR)", f"{orders.count()} ({orders.exclude(status='completed').count()} pending)"),
            ("Active Devices", str(devices.count())),
            ("Failed OTP Attempts (7d)", str(failed_otps_7d)),
        ]
        html = '<table style="border-collapse:collapse;">'
        for label, value in rows:
            html += f'<tr><td style="padding:4px 14px;color:#666;"><b>{label}</b></td><td style="padding:4px 14px;">{value}</td></tr>'
        html += '</table>'
        return mark_safe(html)
    activity_summary.short_description = "Full Activity Overview"