from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    referral_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("full_name", "mobile_number", "password", "referral_code")

    def validate_referral_code(self, value):
        if value:
            value = value.strip().upper()
            if not User.objects.filter(referral_code=value).exists():
                raise serializers.ValidationError("Invalid referral code.")
        return value

    def create(self, validated_data):
        referral_code = validated_data.pop("referral_code", None)
        referred_by_user = None
        if referral_code:
            referred_by_user = User.objects.filter(referral_code=referral_code).first()

        user = User.objects.create_user(
            mobile_number=validated_data["mobile_number"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", "")
        )
        if referred_by_user:
            user.referred_by = referred_by_user
            user.save()
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