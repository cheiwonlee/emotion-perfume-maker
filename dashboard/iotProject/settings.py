"""
Django settings — Daily Mood Perfume Maker 대시보드.

로컬 실습용 설정이다. 배포한다면 환경변수로 DJANGO_SECRET_KEY, DJANGO_DEBUG=0,
DJANGO_ALLOWED_HOSTS 를 지정한다.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 키를 코드에 박아 두지 않고 환경변수로 받는다. (없으면 개발용 키 사용)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "sensor.apps.SensorConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # CSRF 보호는 켜 두고, 보드(수집기)가 호출하는 엔드포인트만 views 에서 @csrf_exempt 로 예외 처리한다.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "iotProject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # 템플릿 대신 web/index.html 을 그대로 내려준다 (sensor/views.py index)
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "iotProject.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "ko"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# 화면(HTML/CSS/JS)은 레포 루트의 web/ 하나를 GitHub Pages·Vercel 과 같이 쓴다.
WEB_DIR = BASE_DIR.parent / "web"
STATIC_URL = "/static/"
STATICFILES_DIRS = [WEB_DIR]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 수집기가 마지막으로 신호를 보낸 뒤 이 시간(초)이 지나면 '연결 끊김'으로 표시
DEVICE_OFFLINE_AFTER_SECONDS = 3
