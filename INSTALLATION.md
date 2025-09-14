# RunQuest Installation Guide

## Системные требования

### Минимальные требования
- **ОС**: Windows 10/11, macOS 10.15+, Ubuntu 18.04+
- **RAM**: 8 GB
- **Диск**: 10 GB свободного места
- **Интернет**: Стабильное подключение

### Рекомендуемые требования
- **ОС**: Windows 11, macOS 12+, Ubuntu 20.04+
- **RAM**: 16 GB
- **Диск**: 20 GB свободного места
- **Интернет**: Высокоскоростное подключение

## Предварительная установка

### 1. Установка Flutter

#### Windows
1. Скачайте Flutter SDK с [официального сайта](https://flutter.dev/docs/get-started/install/windows)
2. Распакуйте архив в `C:\flutter`
3. Добавьте `C:\flutter\bin` в переменную PATH
4. Установите Git для Windows
5. Установите Android Studio или Visual Studio Code

#### macOS
```bash
# Установка через Homebrew
brew install --cask flutter

# Или скачайте с официального сайта
# https://flutter.dev/docs/get-started/install/macos
```

#### Linux (Ubuntu)
```bash
# Скачайте Flutter SDK
cd ~/development
wget https://storage.googleapis.com/flutter_infra_releases/stable/linux/flutter_linux_3.16.0-stable.tar.xz
tar xf flutter_linux_3.16.0-stable.tar.xz

# Добавьте в PATH
export PATH="$PATH:`pwd`/flutter/bin"

# Установите зависимости
sudo apt-get install clang cmake ninja-build pkg-config libgtk-3-dev liblzma-dev
```

### 2. Установка Python

#### Windows
1. Скачайте Python 3.8+ с [python.org](https://www.python.org/downloads/)
2. Убедитесь, что отмечена опция "Add Python to PATH"
3. Установите pip (обычно устанавливается автоматически)

#### macOS
```bash
# Установка через Homebrew
brew install python@3.9

# Или скачайте с python.org
```

#### Linux (Ubuntu)
```bash
sudo apt update
sudo apt install python3.9 python3.9-venv python3.9-dev python3-pip
```

### 3. Установка PostgreSQL с PostGIS

#### Windows
1. Скачайте PostgreSQL с [postgresql.org](https://www.postgresql.org/download/windows/)
2. Установите PostgreSQL
3. Установите PostGIS расширение:
```sql
-- Подключитесь к базе данных и выполните:
CREATE EXTENSION postgis;
```

#### macOS
```bash
# Установка через Homebrew
brew install postgresql postgis

# Запуск PostgreSQL
brew services start postgresql

# Создание базы данных
createdb runquest_db
psql runquest_db -c "CREATE EXTENSION postgis;"
```

#### Linux (Ubuntu)
```bash
# Установка PostgreSQL и PostGIS
sudo apt update
sudo apt install postgresql postgresql-contrib postgis postgresql-12-postgis-3

# Создание базы данных
sudo -u postgres createdb runquest_db
sudo -u postgres psql runquest_db -c "CREATE EXTENSION postgis;"
```

### 4. Установка GDAL (для GeoDjango)

#### Windows
1. Скачайте OSGeo4W с [osgeo.org](https://trac.osgeo.org/osgeo4w/)
2. Установите OSGeo4W
3. Добавьте пути в переменные окружения:
```
GDAL_LIBRARY_PATH=C:\OSGeo4W\bin\gdal310.dll
GEOS_LIBRARY_PATH=C:\OSGeo4W\bin\geos_c.dll
PROJ_LIB=C:\OSGeo4W\share\proj
```

#### macOS
```bash
brew install gdal
```

#### Linux (Ubuntu)
```bash
sudo apt install gdal-bin libgdal-dev
```

## Установка проекта

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd RunQuest
```

### 2. Настройка Backend

#### Создание виртуального окружения
```bash
cd backend
python -m venv .venv

# Активация виртуального окружения
# Windows:
.venv\Scripts\activate

# macOS/Linux:
source .venv/bin/activate
```

#### Установка зависимостей
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Настройка базы данных
1. Создайте базу данных PostgreSQL:
```sql
CREATE DATABASE runquest_db;
CREATE USER runquest_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE runquest_db TO runquest_user;
```

2. Обновите настройки в `backend/backend/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'runquest_db',
        'USER': 'runquest_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

#### Выполнение миграций
```bash
python manage.py makemigrations
python manage.py migrate
```

#### Создание суперпользователя
```bash
python manage.py createsuperuser
```

#### Загрузка тестовых данных (опционально)
```bash
python manage.py loaddata fixtures/initial_data.json
```

### 3. Настройка Frontend

#### Установка зависимостей Flutter
```bash
cd frontend
flutter pub get
```

#### Настройка API URL
Обновите базовый URL API в файлах сервисов:
```dart
// lib/services/auth_service.dart
static const String baseUrl = 'http://localhost:8000/api/';
```

#### Настройка для Android
1. Откройте `android/app/src/main/AndroidManifest.xml`
2. Добавьте разрешения:
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.INTERNET" />
```

#### Настройка для iOS
1. Откройте `ios/Runner/Info.plist`
2. Добавьте разрешения:
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>This app needs location access to track your runs.</string>
<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>This app needs location access to track your runs.</string>
```

## Запуск приложения

### 1. Запуск Backend

#### Через скрипт (Windows)
```bash
start_backend.bat
```

#### Вручную
```bash
cd backend
.venv\Scripts\activate  # Windows
# или
source .venv/bin/activate  # macOS/Linux

python manage.py runserver 0.0.0.0:8000
```

Backend будет доступен по адресу: `http://localhost:8000`

### 2. Запуск Frontend

#### Через скрипт (Windows)
```bash
start_frontend.bat
```

#### Вручную
```bash
cd frontend
flutter run
```

### 3. Проверка установки

1. **Backend API**: Откройте `http://localhost:8000/swagger/` в браузере
2. **Frontend**: Запустите приложение на эмуляторе или устройстве
3. **База данных**: Проверьте подключение через Django admin: `http://localhost:8000/admin/`

## Конфигурация для разработки

### 1. Настройки Django

#### Development Settings
```python
# backend/backend/settings.py
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# CORS настройки для разработки
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
```

#### Environment Variables
Создайте файл `.env` в папке backend:
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=postgresql://runquest_user:password@localhost:5432/runquest_db
```

### 2. Настройки Flutter

#### Debug Configuration
```dart
// lib/config/app_config.dart
class AppConfig {
  static const String apiBaseUrl = 'http://localhost:8000/api/';
  static const bool isDebug = true;
  static const bool enableLogging = true;
}
```

## Устранение неполадок

### Проблемы с Flutter

#### Flutter doctor
```bash
flutter doctor
```

#### Очистка кеша
```bash
flutter clean
flutter pub get
```

#### Проблемы с эмулятором
```bash
# Android
flutter emulators --launch <emulator_id>

# iOS (только macOS)
open -a Simulator
```

### Проблемы с Django

#### Проблемы с GDAL
```bash
# Windows - проверьте пути в settings.py
GDAL_LIBRARY_PATH = 'C:\\OSGeo4W\\bin\\gdal310.dll'

# macOS
brew install gdal

# Linux
sudo apt install gdal-bin libgdal-dev
```

#### Проблемы с базой данных
```bash
# Проверка подключения
python manage.py dbshell

# Сброс миграций (осторожно!)
python manage.py migrate --fake-initial
```

#### Проблемы с зависимостями
```bash
# Обновление pip
pip install --upgrade pip

# Переустановка зависимостей
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### Проблемы с PostgreSQL

#### Проверка статуса
```bash
# Windows
net start postgresql-x64-13

# macOS
brew services start postgresql

# Linux
sudo systemctl start postgresql
```

#### Сброс пароля
```bash
# Linux
sudo -u postgres psql
ALTER USER postgres PASSWORD 'new_password';
```

## Production Deployment

### 1. Настройки для продакшена

#### Django Settings
```python
# backend/backend/settings_production.py
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']
SECRET_KEY = os.environ.get('SECRET_KEY')

# Настройки базы данных
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT'),
    }
}
```

#### Flutter Build
```bash
# Android
flutter build apk --release

# iOS
flutter build ios --release
```

### 2. Docker Deployment

#### Dockerfile для Backend
```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

#### Docker Compose
```yaml
version: '3.8'
services:
  db:
    image: postgis/postgis:13-3.1
    environment:
      POSTGRES_DB: runquest_db
      POSTGRES_USER: runquest_user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgresql://runquest_user:password@db:5432/runquest_db

volumes:
  postgres_data:
```

## Дополнительные ресурсы

- [Flutter Documentation](https://flutter.dev/docs)
- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [PostGIS Documentation](https://postgis.net/documentation/)
- [GeoDjango Documentation](https://docs.djangoproject.com/en/stable/ref/contrib/gis/)
