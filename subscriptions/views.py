from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import razorpay
from django.conf import settings

from .models import Subscription
from .serializers import SubscriptionSerializer


# ─────────────────────────────────────────────────────────────────────────────
# GET  /api/subscriptions/my/
# Returns all subscriptions for the logged-in user.
# Also auto-expires any plans whose expires_at has passed.
# ─────────────────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscriptions(request):
    subs = Subscription.objects.filter(user=request.user)

    # Auto-expire stale active subs (no celery needed for small scale)
    stale = [s for s in subs if s.status == "active" and timezone.now() > s.expires_at]
    for sub in stale:
        sub.status = "expired"
        sub.save(update_fields=["status"])

    serializer = SubscriptionSerializer(subs, many=True)
    return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/subscriptions/activate/
# Called from CheckoutSubscription.jsx after a successful Razorpay payment.
# Body: { module, plan_key, duration, payment_id, amount }
# Creates or updates a subscription row (one per module per user).
# ─────────────────────────────────────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def activate_subscription(request):
    module     = request.data.get("module")
    plan_key   = request.data.get("plan_key", "")
    duration   = request.data.get("duration", "1 Month")
    payment_id = request.data.get("payment_id", "")
    amount     = request.data.get("amount", 0)

    if not module:
        return Response(
            {"error": "module is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Razorpay payment verification ────────────────────────────────────────
    if payment_id:
        try:
            client  = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            payment = client.payment.fetch(payment_id)

            # Confirm the payment is actually captured/authorised
            if payment.get("status") not in ("captured", "authorized"):
                return Response(
                    {"error": "Payment not completed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Confirm the amount matches (Razorpay stores amount in paise)
            if int(payment.get("amount", 0)) != int(float(amount) * 100):
                return Response(
                    {"error": "Payment amount mismatch"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except razorpay.errors.BadRequestError:
            return Response(
                {"error": "Invalid payment ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {"error": "Payment verification failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    # ─────────────────────────────────────────────────────────────────────────

    # Upsert — one subscription per module per user
    sub, created = Subscription.objects.update_or_create(
        user=request.user,
        module=module,
        defaults={
            "plan_key":    plan_key,
            "duration":    duration,
            "status":      "active",
            "payment_id":  payment_id,
            "amount_paid": amount,
            "started_at":  timezone.now(),
            "expires_at":  None,   # triggers _calc_expiry() in save()
        },
    )

    # Force recalculate expires_at (None triggers it inside save)
    sub.expires_at = sub._calc_expiry()
    sub.save(update_fields=["expires_at", "status"])

    return Response(
        SubscriptionSerializer(sub).data,
        status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/subscriptions/cancel/
# Body: { module }
# ─────────────────────────────────────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_subscription(request):
    module = request.data.get("module")
    if not module:
        return Response({"error": "module is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        sub = Subscription.objects.get(user=request.user, module=module)
    except Subscription.DoesNotExist:
        return Response({"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND)

    sub.status = "cancelled"
    sub.save(update_fields=["status"])
    return Response({"detail": f"{module} subscription cancelled."})


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/subscriptions/check/?module=business
# Quick active-check used by permission guards on protected routes.
# ─────────────────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_subscription(request):
    module = request.query_params.get("module")
    if not module:
        return Response({"error": "module query param required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        sub = Subscription.objects.get(user=request.user, module=module)
        return Response({
            "module":     sub.module,
            "is_active":  sub.is_active,
            "days_left":  sub.days_left,
            "hours_left": sub.hours_left,
            "expires_at": sub.expires_at,
            "status":     sub.status,
        })
    except Subscription.DoesNotExist:
        return Response({
            "module":    module,
            "is_active": False,
            "days_left": 0,
        })