from django.urls import path

from .views import (
    CurrentUserView,
    CsrfTokenView,
    EmailVerificationConfirmView,
    EmailVerificationResendView,
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegistrationView,
    SessionStatusView,
)


urlpatterns = [
    path("auth/csrf/", CsrfTokenView.as_view(), name="csrf-token"),
    path("auth/session/", SessionStatusView.as_view(), name="session-status"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/register/", RegistrationView.as_view(), name="register"),
    path(
        "auth/email/verify/",
        EmailVerificationConfirmView.as_view(),
        name="email-verification-confirm",
    ),
    path(
        "auth/email/resend-verification/",
        EmailVerificationResendView.as_view(),
        name="email-verification-resend",
    ),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", CurrentUserView.as_view(), name="current-user"),
    path("auth/password/change/", PasswordChangeView.as_view(), name="password-change"),
    path(
        "auth/password/reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "auth/password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]
