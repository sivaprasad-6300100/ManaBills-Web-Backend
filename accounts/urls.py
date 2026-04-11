from django.urls import path
from .views import SignupView, LoginView, ProtectedView, UsersListView, forgot_password, verify_otp, reset_password

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("protected/", ProtectedView.as_view(), name="protected"),
    path("users/", UsersListView.as_view()),

    # Forgot password flow — 3 endpoints
    path('forgot-password/', forgot_password, name='forgot-password'),
    path('verify-otp/', verify_otp, name='verify-otp'),
    path('reset-password/', reset_password, name='reset-password'),
]