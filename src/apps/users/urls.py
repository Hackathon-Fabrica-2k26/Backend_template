from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    MeResumoView,
    MeView,
    OTPResendView,
    OTPVerifyView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("otp/resend/", OTPResendView.as_view(), name="otp-resend"),
    path("me/", MeView.as_view(), name="me"),
    path("me/resumo/", MeResumoView.as_view(), name="me-resumo"),
]
