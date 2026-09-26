from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import CurrentUserSerializer, LoginSerializer, PasswordChangeSerializer


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["email"].strip().lower(),
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Email or password is incorrect."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response(
            {
                "user": CurrentUserSerializer(user).data,
                "csrfToken": get_token(request),
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)

    @transaction.atomic
    def patch(self, request):
        serializer = CurrentUserSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(CurrentUserSerializer(user).data)


class PasswordChangeView(APIView):
    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["newPassword"])
        request.user.save(update_fields=("password",))
        update_session_auth_hash(request, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
