from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ("full_name","mobile_number", "password")

    def create(self, validated_data):
        user = User.objects.create_user(
            mobile_number=validated_data["mobile_number"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", "")
        )
        return user
    



class LoginSerializer(serializers.Serializer):
    mobile_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        mobile = data.get("mobile_number")
        password = data.get("password")

        try:
            user = User.objects.get(mobile_number=mobile)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        if not user.check_password(password):
            raise serializers.ValidationError("Invalid password")

        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user_id": user.id,
            "full_name": user.full_name,
            "mobile_number": user.mobile_number
        }


class ForgotPasswordSerializer(serializers.Serializer):
    mobile_number = serializers.CharField()

    def validate_mobile_number(self, value):
        if not User.objects.filter(mobile_number=value).exists():
            raise serializers.ValidationError("No account found with this mobile number.")
        return value


class VerifyOtpSerializer(serializers.Serializer):
    mobile_number = serializers.CharField()
    otp = serializers.CharField(max_length=6)


class ResetPasswordSerializer(serializers.Serializer):
    mobile_number = serializers.CharField()
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(min_length=6)