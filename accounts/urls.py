from django.urls import path
from .views import (
    SignupView, LoginView, ProtectedView, UsersListView,
    forgot_password, verify_otp, reset_password,
    send_signup_otp, verify_signup_otp,MyReferralView
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("protected/", ProtectedView.as_view(), name="protected"),
    path("users/", UsersListView.as_view()),

    # Signup OTP (Message Central — replaces Firebase)
    path('send-signup-otp/', send_signup_otp, name='send-signup-otp'),
    path('verify-signup-otp/', verify_signup_otp, name='verify-signup-otp'),

    # Forgot password flow
    path('forgot-password/', forgot_password, name='forgot-password'),
    path('verify-otp/', verify_otp, name='verify-otp'),
    path('reset-password/', reset_password, name='reset-password'),
    path("my-referral/", MyReferralView.as_view(), name="my-referral"),
]