from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from .serializers import SignupSerializer, LoginSerializer, ForgotPasswordSerializer, VerifyOtpSerializer, ResetPasswordSerializer
from accounts.models import User, PasswordResetToken
import random


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User registered successfully"},
                status=status.HTTP_201_CREATED
            )
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



# seeing data manually

# ==================
# ========
class UsersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.all().values("id", "mobile_number")
        return Response(users)
# =======================
# =======================


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """Step 1: User submits mobile → generate OTP"""
    serializer = ForgotPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    mobile = serializer.validated_data['mobile_number']
    user = User.objects.get(mobile_number=mobile)

    # Delete old unused tokens for this user
    PasswordResetToken.objects.filter(user=user, is_used=False).delete()

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))

    PasswordResetToken.objects.create(user=user, otp=otp)

    # TODO: Send OTP via SMS (Twilio / Fast2SMS / MSG91)
    # For now just print to console in development:
    print(f"OTP for {mobile}: {otp}")

    return Response({
        "message": "OTP sent successfully.",
        "otp": otp  # REMOVE THIS IN PRODUCTION — only for dev/testing
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    """Step 2: Verify OTP is valid"""
    serializer = VerifyOtpSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    mobile = serializer.validated_data['mobile_number']
    otp = serializer.validated_data['otp']

    try:
        user = User.objects.get(mobile_number=mobile)
        token = PasswordResetToken.objects.filter(
            user=user, otp=otp, is_used=False
        ).latest('created_at')
    except (User.DoesNotExist, PasswordResetToken.DoesNotExist):
        return Response({"error": "Invalid OTP."}, status=400)

    if token.is_expired:
        return Response({"error": "OTP has expired. Please request a new one."}, status=400)

    return Response({"message": "OTP verified. You can now reset your password."})


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """Step 3: Set new password"""
    serializer = ResetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    mobile = serializer.validated_data['mobile_number']
    otp = serializer.validated_data['otp']
    new_password = serializer.validated_data['new_password']

    try:
        user = User.objects.get(mobile_number=mobile)
        token = PasswordResetToken.objects.filter(
            user=user, otp=otp, is_used=False
        ).latest('created_at')
    except (User.DoesNotExist, PasswordResetToken.DoesNotExist):
        return Response({"error": "Invalid OTP."}, status=400)

    if token.is_expired:
        return Response({"error": "OTP expired. Please request a new one."}, status=400)

    # Set new password
    user.set_password(new_password)
    user.save()

    # Mark token as used
    token.is_used = True
    token.save()

    return Response({"message": "Password reset successfully. Please sign in."})