import re

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from core.serializers import ResolvedImageMixin

User = get_user_model()

# --- registration validation helpers ----------------------------------------
# Mobile numbers are exactly 10 digits. Stripping a leading +91 / 0 keeps pasted
# numbers working, but the stored value is always the bare 10-digit number.
MOBILE_RE = re.compile(r'^\d{10}$')
UPPER_RE = re.compile(r'[A-Z]')
LOWER_RE = re.compile(r'[a-z]')
DIGIT_RE = re.compile(r'\d')
SPECIAL_RE = re.compile(r'[^A-Za-z0-9]')


def normalise_mobile(value):
    digits = re.sub(r'\D', '', value or '')
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    return digits


def password_strength_errors(value):
    """Human-readable list of the strength rules a password still fails."""
    errors = []
    if len(value) < 8:
        errors.append('Password must be at least 8 characters.')
    if not UPPER_RE.search(value):
        errors.append('Password must include an uppercase letter.')
    if not LOWER_RE.search(value):
        errors.append('Password must include a lowercase letter.')
    if not DIGIT_RE.search(value):
        errors.append('Password must include a number.')
    if not SPECIAL_RE.search(value):
        errors.append('Password must include a special character.')
    return errors


class UserSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    avatar_display = serializers.SerializerMethodField()
    booking_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'display_name',
            'role', 'phone', 'address', 'city', 'country', 'avatar_display',
            'is_staff', 'booking_count', 'date_joined', 'marketing_opt_in',
        ]
        read_only_fields = ['id', 'role', 'is_staff', 'date_joined', 'booking_count']

    def get_avatar_display(self, obj):
        return self.resolved(obj.avatar, obj.avatar_url)


class UserUpdateSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    avatar_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone', 'address', 'city', 'country',
            'avatar', 'avatar_url', 'avatar_display', 'marketing_opt_in',
        ]

    def get_avatar_display(self, obj):
        return self.resolved(obj.avatar, obj.avatar_url)


class RegisterSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=True, min_length=3, max_length=150)
    last_name = serializers.CharField(required=True, min_length=1, max_length=150)
    username = serializers.CharField(required=True, min_length=3, max_length=150)
    phone = serializers.CharField(required=True, max_length=40)
    # Profile details captured once at sign-up and reused across the site
    # (dashboard profile, bookings, support). Stored on the same user row, so
    # there is no separate profile record to fall out of sync.
    city = serializers.CharField(required=True, max_length=120)
    country = serializers.CharField(required=True, max_length=120)
    address = serializers.CharField(required=True, max_length=255)
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 'phone',
            'city', 'country', 'address',
            'password', 'password_confirm',
        ]

    def validate_first_name(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('First name must be at least 3 characters.')
        return value

    def validate_last_name(self, value):
        value = value.strip()
        if len(value) < 1:
            raise serializers.ValidationError('Last name is required.')
        return value

    def validate_phone(self, value):
        digits = normalise_mobile(value)
        if not MOBILE_RE.match(digits):
            raise serializers.ValidationError('Enter a valid 10-digit mobile number.')
        return digits

    def validate_city(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('City is required.')
        return value

    def validate_country(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Country is required.')
        return value

    def validate_address(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Address is required.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value.lower()

    def validate_username(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Username must be at least 3 characters.')
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        validate_password(attrs['password'])
        strength_errors = password_strength_errors(attrs['password'])
        if strength_errors:
            raise serializers.ValidationError({'password': strength_errors})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text='Username or email address.')
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get('request'),
            username=attrs.get('username'),
            password=attrs.get('password'),
        )
        if not user:
            raise serializers.ValidationError({'detail': 'Invalid credentials.'})
        if not user.is_active:
            raise serializers.ValidationError({'detail': 'This account has been disabled.'})
        attrs['user'] = user
        return attrs
