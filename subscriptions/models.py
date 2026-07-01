# Create your models here.
from django.db import models
from django.utils import timezone
from datetime import timedelta
from accounts.models import User


class Subscription(models.Model):

    MODULE_CHOICES = [
        ("business",      "Business Billing"),
        ("home-expense",  "Home Expenses"),
        ("construction",  "Construction"),
        ("custom",        "Custom"),
    ]

    DURATION_CHOICES = [
        ("1 Month",    "1 Month"),
        ("6 Months",   "6 Months"),
        ("1 Year",     "1 Year"),
        ("FREE_TRIAL", "Free Trial"),
    ]

    STATUS_CHOICES = [
        ("active",    "Active"),
        ("expired",   "Expired"),
        ("cancelled", "Cancelled"),
    ]

    user        = models.ForeignKey(
                      User,
                      on_delete=models.CASCADE,
                      related_name="subscriptions",
                  )
    module      = models.CharField(max_length=30, choices=MODULE_CHOICES)
    plan_key    = models.CharField(max_length=50, blank=True, default="")
    # e.g. "business_basic", "business_pro", "home_basic" …
    duration    = models.CharField(max_length=20, choices=DURATION_CHOICES)
    status      = models.CharField(
                      max_length=15,
                      choices=STATUS_CHOICES,
                      default="active",
                  )
    payment_id  = models.CharField(max_length=100, blank=True, default="")
    # Razorpay payment ID e.g. "pay_XXXXXXXXXX"
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    started_at  = models.DateTimeField(default=timezone.now)
    expires_at  = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        # One active subscription per module per user
        unique_together = ["user", "module"]
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    def __str__(self):
        return f"{self.user} — {self.module} — {self.duration} — {self.status}"

    # ------------------------------------------------------------------ #
    # Expiry calculation
    # ------------------------------------------------------------------ #
    def _calc_expiry(self):
        base = self.started_at or timezone.now()
        mapping = {
            "1 Year":    timedelta(days=365),
            "6 Months":  timedelta(days=182),
            "1 Month":    timedelta(days=30),
            "FREE_TRIAL": timedelta(days=7),
        }
        # Default → 1 Month (30 days)
        return base + mapping.get(self.duration, timedelta(days=30))

    def save(self, *args, **kwargs):
        # Auto-calculate expires_at on first save or when explicitly cleared
        if not self.expires_at:
            self.expires_at = self._calc_expiry()

        # Auto-update status if the plan has passed its expiry date
        if self.expires_at and timezone.now() > self.expires_at:
            self.status = "expired"

        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Convenience properties
    # ------------------------------------------------------------------ #
    @property
    def is_active(self):
        return self.status == "active" and timezone.now() < self.expires_at

    @property
    def days_left(self):
        if not self.expires_at:
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    @property
    def hours_left(self):
        """Useful for the frontend countdown chip in Topbar."""
        if not self.expires_at:
            return 0
        delta = self.expires_at - timezone.now()
        total_seconds = delta.total_seconds()
        return max(0, total_seconds / 3600)
