from django.urls import path

from .views import (
    CurrentUserView,
    CsrfTokenView,
    LoginView,
    LogoutView,
    PasswordChangeView,
    SessionStatusView,
)


urlpatterns = [
    path("auth/csrf/", CsrfTokenView.as_view(), name="csrf-token"),
    path("auth/session/", SessionStatusView.as_view(), name="session-status"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", CurrentUserView.as_view(), name="current-user"),
    path("auth/password/change/", PasswordChangeView.as_view(), name="password-change"),
]
