from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)
import uuid
from django.utils import timezone
from datetime import timedelta

import random
import string


class UserManager(BaseUserManager):
    def create_user(self, password=None, mobile_number=None, **extra_fields):
        if not mobile_number:
            raise ValueError("User must have a mobile number")

        user = self.model(
            mobile_number=mobile_number,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, password, mobile_number=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        return self.create_user(
            password=password,
            mobile_number=mobile_number,
            **extra_fields
        )


class User(AbstractBaseUser, PermissionsMixin):
    full_name = models.CharField(
        max_length=100, blank=True
        
    )
    mobile_number = models.CharField(
        max_length=15,
        unique=True
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    referral_code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )

    objects = UserManager()

    USERNAME_FIELD = 'mobile_number'
    REQUIRED_FIELDS = []


    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = generate_referral_code()
        super().save(*args, **kwargs)
        

    def __str__(self):
        return self.mobile_number or self.full_name


class OtpSession(models.Model):
    PURPOSE_CHOICES = (
        ("signup", "Signup"),
        ("reset", "Reset"),
        ("customer", "Customer Login"),
    )

    mobile_number = models.CharField(max_length=15)
    verification_id = models.CharField(max_length=50)
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)
    





def generate_referral_code():
    """Generates a unique MB + 6 alphanumeric char code, e.g. MB4X9K2A"""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "MB" + "".join(random.choices(chars, k=6))
        if not User.objects.filter(referral_code=code).exists():
            return code