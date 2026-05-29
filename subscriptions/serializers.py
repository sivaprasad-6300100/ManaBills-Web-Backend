from rest_framework import serializers
from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):

    # Read-only computed fields from model properties
    is_active  = serializers.BooleanField(read_only=True)
    days_left  = serializers.IntegerField(read_only=True)
    hours_left = serializers.FloatField(read_only=True)

    class Meta:
        model  = Subscription
        fields = [
            "id",
            "module",
            "plan_key",
            "duration",
            "status",
            "payment_id",
            "amount_paid",
            "started_at",
            "expires_at",
            "is_active",
            "days_left",
            "hours_left",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "started_at",
            "created_at",
            "updated_at",
            "is_active",
            "days_left",
            "hours_left",
        ]
