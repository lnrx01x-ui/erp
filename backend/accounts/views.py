import logging
import smtplib

from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError
from django.db import transaction
from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.encoding import force_bytes
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditEvent
from .serializers import (
    CurrentUserSerializer,
    EmailVerificationConfirmSerializer,
    EmailVerificationResendSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
)
from .tokens import email_verification_token_generator

logger = logging.getLogger(__name__)


class EmailDeliveryUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "تعذر إرسال رسالة التفعيل حاليًا. حاول مرة أخرى لاحقًا."


def send_email_verification(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token_generator.make_token(user)
    verification_url = (
        f"{settings.PUBLIC_APP_URL}/#email_verification=1"
        f"&uid={uid}&token={token}"
    )
    try:
        send_mail(
            subject="تأكيد البريد الإلكتروني لحساب نسق",
            message=(
                "أهلًا بك في نسق.\n"
                "أكد ملكية بريدك الإلكتروني وفعّل حسابك من الرابط التالي:\n"
                f"{verification_url}\n\n"
                "إذا لم تنشئ هذا الحساب، يمكنك تجاهل هذه الرسالة."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except (OSError, RuntimeError, ValueError, smtplib.SMTPException) as error:
        logger.exception("Could not send an account verification email.")
        raise EmailDeliveryUnavailable() from error


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class SessionStatusView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response({"authenticated": request.user.is_authenticated})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"

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
        AuditEvent.objects.create(
            actor=user,
            action="user.logged_in",
            entity_type="user",
            entity_id=str(user.id),
            metadata={"email": user.email},
        )
        return Response(
            {
                "user": CurrentUserSerializer(user).data,
                "csrfToken": get_token(request),
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class RegistrationView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "registration"

    @transaction.atomic
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            email = serializer.validated_data["email"]
            if get_user_model().objects.filter(email__iexact=email).exists():
                return Response(
                    {"email": "هذا البريد الإلكتروني مسجل بالفعل."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        if not settings.REQUIRE_EMAIL_VERIFICATION:
            login(request, user)
            return Response(
                {
                    "user": CurrentUserSerializer(user).data,
                    "csrfToken": get_token(request),
                },
                status=status.HTTP_201_CREATED,
            )

        send_email_verification(user)
        return Response(
            {
                "detail": (
                    "تم إنشاء الحساب. افتح رسالة التفعيل المرسلة إلى بريدك "
                    "الإلكتروني لإكمال التسجيل."
                )
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        AuditEvent.objects.create(
            actor=request.user,
            action="user.logged_out",
            entity_type="user",
            entity_id=str(request.user.id),
            metadata={"email": request.user.email},
        )
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)

    @transaction.atomic
    def patch(self, request):
        old_values = {
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "phone": request.user.phone,
        }
        serializer = CurrentUserSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        new_values = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
        }
        changes = {
            key: {"old": old_values[key], "new": new_values[key]}
            for key in old_values
            if old_values[key] != new_values[key]
        }
        if changes:
            AuditEvent.objects.create(
                actor=request.user,
                action="user.profile_updated",
                entity_type="user",
                entity_id=str(user.id),
                metadata={"changes": changes},
            )
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
        AuditEvent.objects.create(
            actor=request.user,
            action="user.password_changed",
            entity_type="user",
            entity_id=str(request.user.id),
            metadata={},
        )
        update_session_auth_hash(request, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetRequestView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = get_user_model().objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = (
                f"{settings.PUBLIC_APP_URL}/#password_reset=1"
                f"&uid={uid}&token={token}"
            )
            try:
                send_mail(
                    subject="إعادة تعيين كلمة مرور حساب نسق",
                    message=(
                        "وصلنا طلب لإعادة تعيين كلمة مرور حسابك في نسق.\n"
                        "افتح الرابط التالي لإدخال كلمة مرور جديدة:\n"
                        f"{reset_url}\n\n"
                        "إذا لم تطلب ذلك، يمكنك تجاهل هذه الرسالة."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except (OSError, RuntimeError, ValueError, smtplib.SMTPException):
                logger.exception("Could not send a password-reset email.")
                return Response(
                    {"detail": "تعذر إرسال رسالة الاستعادة حاليًا. حاول لاحقًا."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        return Response(
            {
                "detail": (
                    "إذا كان البريد مسجلًا، فستصلك رسالة تحتوي على خطوات "
                    "إعادة تعيين كلمة المرور."
                )
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetConfirmView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_model = get_user_model()
        try:
            user_id = user_model._meta.pk.to_python(
                urlsafe_base64_decode(serializer.validated_data["uid"]).decode()
            )
            user = user_model.objects.get(pk=user_id, is_active=True)
        except (
            ValueError,
            TypeError,
            UnicodeError,
            DjangoValidationError,
            user_model.DoesNotExist,
        ):
            return Response(
                {"detail": "رابط الاستعادة غير صالح أو انتهت صلاحيته."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(
            user,
            serializer.validated_data["token"],
        ):
            return Response(
                {"detail": "رابط الاستعادة غير صالح أو انتهت صلاحيته."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_password = serializer.validated_data["newPassword"]
        try:
            validate_password(new_password, user)
        except DjangoValidationError as error:
            return Response(
                {"newPassword": error.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user.set_password(new_password)
            user.save(update_fields=("password",))
            AuditEvent.objects.create(
                actor=user,
                action="user.password_reset",
                entity_type="user",
                entity_id=str(user.id),
                metadata={},
            )
        return Response({"detail": "تم تحديث كلمة المرور. يمكنك تسجيل الدخول الآن."})


@method_decorator(csrf_protect, name="dispatch")
class EmailVerificationConfirmView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = EmailVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_model = get_user_model()
        try:
            user_id = user_model._meta.pk.to_python(
                urlsafe_base64_decode(serializer.validated_data["uid"]).decode()
            )
            user = user_model.objects.get(pk=user_id)
        except (
            ValueError,
            TypeError,
            UnicodeError,
            DjangoValidationError,
            user_model.DoesNotExist,
        ):
            return Response(
                {"detail": "رابط التفعيل غير صالح أو انتهت صلاحيته."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            user.is_active
            or user.email_verified
            or not email_verification_token_generator.check_token(
                user,
                serializer.validated_data["token"],
            )
        ):
            return Response(
                {"detail": "رابط التفعيل غير صالح أو انتهت صلاحيته."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user.is_active = True
            user.email_verified = True
            user.save(update_fields=("is_active", "email_verified"))
            AuditEvent.objects.create(
                actor=user,
                action="user.email_verified",
                entity_type="user",
                entity_id=str(user.id),
                metadata={},
            )
        return Response({"detail": "تم تأكيد البريد وتفعيل الحساب. يمكنك تسجيل الدخول."})


@method_decorator(csrf_protect, name="dispatch")
class EmailVerificationResendView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "email_verification"

    def post(self, request):
        serializer = EmailVerificationResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_user_model().objects.filter(
            email__iexact=serializer.validated_data["email"].strip().lower(),
            is_active=False,
            email_verified=False,
        ).first()
        if user:
            send_email_verification(user)
        return Response(
            {
                "detail": (
                    "إذا كان هناك حساب غير مفعّل بهذا البريد، فستصلك رسالة "
                    "تفعيل جديدة."
                )
            }
        )
