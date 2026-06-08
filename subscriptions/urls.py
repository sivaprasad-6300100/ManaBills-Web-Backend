from django.urls import path
from . import views

urlpatterns = [
    # Returns all subscriptions for logged-in user
    path("my/",      views.my_subscriptions,   name="my-subscriptions"),

    # Called after Razorpay payment success
    path("activate/", views.activate_subscription, name="activate-subscription"),

    # Cancel a module subscription
    path("cancel/",   views.cancel_subscription,   name="cancel-subscription"),

    # Quick active-check: /api/subscriptions/check/?module=business
    path("check/",    views.check_subscription,    name="check-subscription"),


    path("free-trial/", views.activate_free_trial),
]
