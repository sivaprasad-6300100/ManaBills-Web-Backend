import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from .serializers import SignupSerializer, LoginSerializer, ForgotPasswordSerializer, VerifyOtpSerializer, ResetPasswordSerializer
from accounts.models import User, OtpSession
from accounts.otp_utils import send_otp, validate_otp


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        mobile = request.data.get("mobile_number")

        session = OtpSession.objects.filter(
            mobile_number=mobile, purpose="signup", is_verified=True, is_used=False
        ).order_by("-created_at").first()

        if not session or session.is_expired:
            return Response({"error": "Please verify your mobile number first."}, status=400)

        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            session.is_used = True
            session.save()
            return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "message": "You are authenticated",
            "user_id": request.user.id,
            "mobile_number": request.user.mobile_number
        })


class UsersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.all().values("id", "mobile_number")
        return Response(users)


# ─── SIGNUP OTP (replaces Firebase) ───

@api_view(['POST'])
@permission_classes([AllowAny])
def send_signup_otp(request):
    mobile = (request.data.get("mobile_number") or "").strip()
    if not re.match(r'^\d{10}$', mobile):
        return Response({"error": "Enter a valid 10-digit mobile number."}, status=400)

    if User.objects.filter(mobile_number=mobile).exists():
        return Response({"error": "Mobile number already registered."}, status=400)

    OtpSession.objects.filter(mobile_number=mobile, purpose="signup", is_used=False).delete()

    try:
        verification_id = send_otp(mobile)
    except Exception:
        return Response({"error": "Failed to send OTP. Try again."}, status=500)

    OtpSession.objects.create(mobile_number=mobile, verification_id=verification_id, purpose="signup")
    return Response({"message": "OTP sent successfully."})


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_signup_otp(request):
    mobile = (request.data.get("mobile_number") or "").strip()
    code = (request.data.get("otp") or "").strip()

    session = OtpSession.objects.filter(
        mobile_number=mobile, purpose="signup", is_used=False
    ).order_by("-created_at").first()

    if not session:
        return Response({"error": "No OTP request found. Please request a new OTP."}, status=400)

    if session.is_expired:
        return Response({"error": "OTP expired. Please request a new one."}, status=400)

    if validate_otp(session.verification_id, code):
        session.is_verified = True
        session.save()
        return Response({"message": "Mobile number verified successfully."})

    return Response({"error": "Invalid OTP. Please try again."}, status=400)


# ─── FORGOT PASSWORD (now uses real SMS instead of console-printed OTP) ───

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    serializer = ForgotPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    mobile = serializer.validated_data['mobile_number']

    if not User.objects.filter(mobile_number=mobile).exists():
        return Response({"error": "Mobile number not found."}, status=400)

    OtpSession.objects.filter(mobile_number=mobile, purpose="reset", is_used=False).delete()

    try:
        verification_id = send_otp(mobile)
    except Exception:
        return Response({"error": "Failed to send OTP. Try again."}, status=500)

    OtpSession.objects.create(mobile_number=mobile, verification_id=verification_id, purpose="reset")
    return Response({"message": "OTP sent successfully."})


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    serializer = VerifyOtpSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    mobile = serializer.validated_data['mobile_number']
    otp = serializer.validated_data['otp']

    session = OtpSession.objects.filter(
        mobile_number=mobile, purpose="reset", is_used=False
    ).order_by("-created_at").first()

    if not session:
        return Response({"error": "Invalid OTP."}, status=400)

    if session.is_expired:
        return Response({"error": "OTP has expired. Please request a new one."}, status=400)

    if not validate_otp(session.verification_id, otp):
        return Response({"error": "Invalid OTP."}, status=400)

    session.is_verified = True
    session.save()
    return Response({"message": "OTP verified. You can now reset your password."})


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    serializer = ResetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    mobile = serializer.validated_data['mobile_number']
    new_password = serializer.validated_data['new_password']

    session = OtpSession.objects.filter(
        mobile_number=mobile, purpose="reset", is_verified=True, is_used=False
    ).order_by("-created_at").first()

    if not session:
        return Response({"error": "Please verify OTP again."}, status=400)

    if session.is_expired:
        return Response({"error": "Session expired. Please start again."}, status=400)

    user = User.objects.get(mobile_number=mobile)
    user.set_password(new_password)
    user.save()

    session.is_used = True
    session.save()

    return Response({"message": "Password reset successfully. Please sign in."})