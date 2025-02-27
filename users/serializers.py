from rest_framework import serializers, exceptions
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from django.contrib.auth.hashers import check_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import smart_bytes, force_str

from .models import User, Profile, LoggedIn, BlockedCountryIP
from .tasks import send_email
from .validators import (
    password_validator,
    password_pattern,
    username_validator,
    nickname_validator,
)

from reviews.serializers import ReviewListSerializer
from places.serializers import PlaceSerializer


# 회원가입 serializer
class SignupSerializer(serializers.ModelSerializer):
    repassword = serializers.CharField(
        error_messages={
            "required": "비밀번호를 입력해주세요.",
            "blank": "비밀번호를 입력해주세요.",
            "write_only": True,
        }
    )
    term_check = serializers.BooleanField(
        error_messages={
            "required": "약관동의를 확인해주세요.",
            "blank": "약관동의를 확인해주세요.",
            "write_only": True,
        }
    )

    class Meta:
        model = User
        fields = (
            "username",
            "password",
            "repassword",
            "phone_number",
            "email",
            "term_check",
        )
        extra_kwargs = {
            "username": {
                "error_messages": {
                    "required": "아이디를 입력해주세요.",
                    "blank": "아이디를 입력해주세요",
                }
            },
            "password": {
                "write_only": True,
                "error_messages": {
                    "required": "비밀번호를 입력해주세요.",
                    "blank": "비밀번호를 입력해주세요.",
                },
            },
            "email": {
                "error_messages": {
                    "required": "이메일을 입력해주세요.",
                    "invalid": "알맞은 형식의 이메일을 입력해주세요.",
                    "blank": "이메일을 입력해주세요.",
                }
            },
            "phone_number": {
                "error_messages": {
                    "required": "휴대폰 번호를 입력해주세요.",
                }
            },
        }

    def validate(self, data):
        username = data.get("username")
        phone_number = data.get("phone_number")
        password = data.get("password")
        repassword = data.get("repassword")
        term_check = data.get("term_check")

        # 아이디 유효성 검사
        if username_validator(username):
            raise serializers.ValidationError(detail={"username": "아이디는 6자 이상 20자 이하의 숫자, 영문 대/소문자 이어야 합니다."})

        # 비밀번호 일치
        if password != repassword:
            raise serializers.ValidationError(detail={"password": "비밀번호가 일치하지 않습니다."})

        # 비밀번호 유효성 검사
        if password_validator(password):
            raise serializers.ValidationError(detail={"password": "비밀번호는 8자 이상 16자이하의 영문 대/소문자, 숫자, 특수문자 조합이어야 합니다. "})

        # 비밀번호 동일여부 검사
        if password_pattern(password):
            raise serializers.ValidationError(detail={"password": "비밀번호는 3자리 이상 동일한 영문,숫자,특수문자 사용 불가합니다. "})

        # 휴대폰 번호 존재여부와 blank 허용
        if (User.objects.filter(phone_number=phone_number).exists() and not phone_number == ""):
            raise serializers.ValidationError(detail={"phone_number": "이미 사용중인 휴대폰 번호 이거나 탈퇴한 휴대폰 번호입니다."})

        # 이용약관 확인 검사
        if term_check == False:
            raise serializers.ValidationError(detail={"term_check": "약관동의를 확인해주세요."})

        return data

    def create(self, validated_data):
        username = validated_data["username"]
        email = validated_data["email"]
        phone_number = validated_data["phone_number"]

        user = User(
            username=username,
            phone_number=phone_number,
            email=email,
        )
        user.set_password(validated_data["password"])
        user.save()

        Profile.objects.create(user=user)
        return user


# 회원정보 수정 serializer
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "email",
            "phone_number",
        )
        extra_kwargs = {
            "email": {
                "error_messages": {
                    "required": "이메일을 입력해주세요.",
                    "invalid": "알맞은 형식의 이메일을 입력해주세요.",
                    "blank": "이메일을 입력해주세요.",
                }
            },
            "phone_number": {
                "error_messages": {
                    "required": "휴대폰 번호를 입력해주세요.",
                }
            },
        }

    def validate(self, data):
        phone_number = data.get("phone_number")
        current_phone_number = self.context.get("request").user.phone_number

        # 휴대폰 번호 존재여부와 blank 허용
        if (User.objects.filter(phone_number=phone_number).exclude(phone_number=current_phone_number).exists() and not phone_number == ""):
            raise serializers.ValidationError(detail={"phone_number": "이미 사용중인 휴대폰 번호 이거나 탈퇴한 휴대폰 번호입니다."})

        return data

    def update(self, instance, validated_data):
        instance.email = validated_data.get("email", instance.email)
        instance.phone_number = validated_data.get("phone_number", instance.phone_number)
        instance.save()

        return instance


# 로그아웃 serializer
class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        self.token = attrs["refresh"]
        return attrs

    def save(self, **kwargs):
        try:
            RefreshToken(self.token).blacklist()

        except TokenError:
            raise serializers.ValidationError(detail={"만료된 토큰": "유효하지 않거나 만료된 토큰입니다."})


# 개인 프로필 serializer
class PrivateProfileSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    is_confirmed = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()

    def get_email(self, obj):
        return obj.user.email

    def get_username(self, obj):
        return obj.user.username

    def get_is_confirmed(self, obj):
        return obj.user.is_confirmed

    def get_phone_number(self, obj):
        return obj.user.phone_number

    class Meta:
        model = Profile
        fields = (
            "id",
            "nickname",
            "profile_image",
            "email",
            "username",
            "intro",
            "is_confirmed",
            "phone_number",
        )


# 공개 프로필 serializer
class PublicProfileSerializer(serializers.ModelSerializer):
    followings = PrivateProfileSerializer(many=True)
    followers = PrivateProfileSerializer(many=True)
    review_set = ReviewListSerializer(many=True, source="user.review_set")
    bookmark_place = PlaceSerializer(many=True, source="user.bookmark_place")
    user_id = serializers.SerializerMethodField()

    def get_user_id(self, obj):
        return obj.user.id

    class Meta:
        model = Profile
        fields = (
            "id",
            "user_id",
            "nickname",
            "profile_image",
            "intro",
            "followings",
            "followers",
            "review_set",
            "bookmark_place",
        )


# 프로필 편집 serializer
class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = (
            "nickname",
            "profile_image",
            "intro",
        )
        extra_kwargs = {
            "nickname": {
                "error_messages": {
                    "required": "닉네임을 입력해주세요.",
                    "blank": "닉네임을 입력해주세요.",
                }
            },
            "intro": {
                "error_messages": {
                    "required": "자기소개를 입력해주세요.",
                    "blank": "자기소개를 입력해주세요.",
                }
            },
        }

    def validate(self, data):
        nickname = data.get("nickname")

        # 닉네임 유효성 검사
        if nickname_validator(nickname):
            raise serializers.ValidationError(detail={"nickname": "닉네임은 3자이상 10자 이하로 작성해야하며 특수문자는 포함할 수 없습니다."})

        return data

    def update(self, instance, validated_data):
        instance.nickname = validated_data.get("nickname", instance.nickname)
        instance.profile_image = validated_data.get("profile_image", instance.profile_image)
        instance.intro = validated_data.get("intro", instance.intro)
        instance.save()

        return instance


# 로그인 로그 serializer
class LoginLogListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoggedIn
        fields = (
            "updated_ip",
            "country",
            "created_at",
        )


# 국가 코드 Ip차단 serializer
class CountyIPBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedCountryIP
        fields = (
            "id",
            "country",
            "created_at",
        )


class CountyIPBlockCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedCountryIP
        fields = ("country",)
        extra_kwargs = {
            "country": {
                "error_messages": {
                    "required": "국가코드를 선택해주세요.",
                    "blank": "국가코드를 선택해주세요.",
                }
            },
        }


# 비밀번호 변경 serializer
class ChangePasswordSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(
        error_messages={
            "required": "비밀번호를 입력해주세요.",
            "blank": "비밀번호를 입력해주세요.",
            "write_only": True,
        }
    )
    repassword = serializers.CharField(
        error_messages={
            "required": "비밀번호를 입력해주세요.",
            "blank": "비밀번호를 입력해주세요.",
            "write_only": True,
        }
    )

    class Meta:
        model = User
        fields = (
            "password",
            "repassword",
            "confirm_password",
        )
        extra_kwargs = {
            "password": {
                "write_only": True,
                "error_messages": {
                    "required": "비밀번호를 입력해주세요.",
                    "blank": "비밀번호를 입력해주세요.",
                },
            },
        }

    def validate(self, data):
        current_password = self.context.get("request").user.password
        confirm_password = data.get("confirm_password")
        password = data.get("password")
        repassword = data.get("repassword")

        # 현재 비밀번호 예외 처리
        if not check_password(confirm_password, current_password):
            raise serializers.ValidationError(detail={"password": "현재 비밀번호가 일치하지 않습니다."})

        # 현재 비밀번호와 바꿀 비밀번호 비교
        if check_password(password, current_password):
            raise serializers.ValidationError(detail={"password": "현재 사용중인 비밀번호와 동일한 비밀번호는 입력할 수 없습니다."})

        # 비밀번호 일치
        if password != repassword:
            raise serializers.ValidationError(detail={"password": "비밀번호가 일치하지 않습니다."})

        # 비밀번호 유효성 검사
        if password_validator(password):
            raise serializers.ValidationError(detail={"password": "비밀번호는 8자 이상 16자이하의 영문 대/소문자, 숫자, 특수문자 조합이어야 합니다. "})

        # 비밀번호 문자열 동일여부 검사
        if password_pattern(password):
            raise serializers.ValidationError(detail={"password": "비밀번호는 3자리 이상 동일한 영문/사용 사용 불가합니다. "})

        return data

    def update(self, instance, validated_data):
        instance.password = validated_data.get("password", instance.password)
        instance.set_password(instance.password)
        instance.save()

        return instance


# 비밀번호 찾기 serializer
class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(
        error_messages={
            "required": "이메일을 입력해주세요.",
            "blank": "이메일을 입력해주세요.",
            "invalid": "알맞은 형식의 이메일을 입력해주세요.",
        }
    )

    class Meta:
        fields = ("email",)

    def validate(self, attrs):
        email = attrs.get("email")

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            uidb64 = urlsafe_base64_encode(smart_bytes(user.id))
            token = PasswordResetTokenGenerator().make_token(user)  

            frontend_site = "www.gaggamagga.shop"
            absurl = f"https://{frontend_site}/set_password.html?/{uidb64}/{token}/"  
            email_body = "안녕하세요? \n 비밀번호 재설정 주소입니다.\n" + absurl  
            message = {
                "email_body": email_body,
                "to_email": user.email,
                "email_subject": "비밀번호 재설정",
            }
            send_email.delay(message)

            return super().validate(attrs)
        raise serializers.ValidationError(detail={"email": "잘못된 이메일입니다. 다시 입력해주세요."})


# 비밀번호 재설정 serializer
class SetNewPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(
        error_messages={
            "required": "비밀번호를 입력해주세요.",
            "blank": "비밀번호를 입력해주세요.",
            "write_only": True,
        }
    )
    repassword = serializers.CharField(
        error_messages={
            "required": "비밀번호를 입력해주세요.",
            "blank": "비밀번호를 입력해주세요.",
            "write_only": True,
        }
    )
    token = serializers.CharField(max_length=100, write_only=True)
    uidb64 = serializers.CharField(max_length=100, write_only=True)

    class Meta:
        fields = (
            "repassword",
            "password",
            "token",
            "uidb64",
        )

    def validate(self, attrs):
        password = attrs.get("password")
        repassword = attrs.get("repassword")
        token = attrs.get("token")
        uidb64 = attrs.get("uidb64")

        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(id=user_id)

        # 토큰이 유효여부
        if PasswordResetTokenGenerator().check_token(user, token) == False:
            raise exceptions.AuthenticationFailed("링크가 유효하지 않습니다.", 401)

        # 비밀번호 일치
        if password != repassword:
            raise serializers.ValidationError(detail={"password": "비밀번호가 일치하지 않습니다."})

        # 비밀번호 유효성 검사
        if password_validator(password):
            raise serializers.ValidationError(detail={"password": "비밀번호는 8자 이상 16자이하의 영문 대/소문자, 숫자, 특수문자 조합이어야 합니다."})

        # 비밀번호 문자열 동일여부 검사
        if password_pattern(password):
            raise serializers.ValidationError(detail={"password": "비밀번호는 3자리 이상 동일한 영문/사용 사용 불가합니다."})

        user.set_password(password)
        user.save()

        return super().validate(attrs)