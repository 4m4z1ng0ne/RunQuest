# GitHub Setup Guide для RunQuest

Этот документ содержит пошаговые инструкции по выгрузке проекта RunQuest на GitHub для портфолио.

## Подготовка к выгрузке

### 1. Проверка структуры проекта

Убедитесь, что в корневой папке проекта есть следующие файлы:

```
RunQuest/
├── README.md                 ✅ Основная документация
├── API_DOCUMENTATION.md      ✅ Документация API
├── ARCHITECTURE.md           ✅ Архитектурная документация
├── INSTALLATION.md           ✅ Инструкции по установке
├── PORTFOLIO_INFO.md         ✅ Информация для портфолио
├── CONTRIBUTING.md           ✅ Руководство по участию
├── LICENSE                   ✅ Лицензия MIT
├── .gitignore               ✅ Игнорирование файлов
├── screenshots/             ✅ Папка для скриншотов
├── frontend/                ✅ Flutter приложение
├── backend/                 ✅ Django API
└── Documentation/           ✅ Документация проекта
```

### 2. Финальная проверка .gitignore

Убедитесь, что `.gitignore` файлы правильно настроены:

- **Корневой .gitignore** - для всего проекта
- **backend/.gitignore** - для Django backend
- **frontend/.gitignore** - для Flutter frontend

### 3. Очистка проекта

Удалите все временные файлы:
- Логи ошибок (`hs_err_*.log`)
- Файлы сборки (`build/`, `__pycache__/`)
- Временные файлы (`.tmp`, `.temp`)
- Локальные настройки (`.env`, `local.properties`)

## Создание репозитория на GitHub

### 1. Создание нового репозитория

1. Войдите в GitHub
2. Нажмите "New repository"
3. Заполните поля:
   - **Repository name**: `RunQuest`
   - **Description**: `🏃‍♂️ Full-stack running app with Flutter frontend and Django REST API backend. Features GPS tracking, gamification, and social features.`
   - **Visibility**: Public (для портфолио)
   - **Initialize**: НЕ отмечайте "Add a README file" (у нас уже есть)

### 2. Настройка репозитория

Добавьте темы (topics) для лучшей видимости:
- `flutter`
- `django`
- `mobile-app`
- `gps-tracking`
- `rest-api`
- `postgis`
- `gamification`
- `portfolio`
- `full-stack`

## Инициализация Git и выгрузка

### 1. Инициализация Git репозитория

```bash
# Перейдите в папку проекта
cd RunQuest

# Инициализируйте Git
git init

# Добавьте все файлы
git add .

# Сделайте первый коммит
git commit -m "Initial commit: RunQuest - Full-stack running app

- Flutter frontend with GPS tracking
- Django REST API backend with PostGIS
- Gamification system with achievements and challenges
- Social features with friends and activity feed
- Complete documentation and setup instructions"
```

### 2. Подключение к GitHub

```bash
# Добавьте remote origin (замените YOUR_USERNAME на ваш GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/RunQuest.git

# Установите основную ветку
git branch -M main

# Выгрузите код
git push -u origin main
```

### 3. Проверка выгрузки

1. Откройте репозиторий на GitHub
2. Убедитесь, что все файлы загружены
3. Проверьте, что README.md отображается корректно

## Настройка репозитория

### 1. Описание репозитория

Добавьте краткое описание в настройках репозитория:
```
🏃‍♂️ Full-stack running app with Flutter frontend and Django REST API backend. Features GPS tracking, gamification, and social features.
```

### 2. Сайт репозитория

Если у вас есть демо-версия, добавьте ссылку в настройках:
- **Website**: `https://your-demo-site.com`
- **Topics**: Добавьте темы, указанные выше

### 3. Настройка Issues и Projects

Включите:
- ✅ Issues
- ✅ Projects
- ✅ Wiki (опционально)

## Создание Releases

### 1. Первый релиз

1. Перейдите в раздел "Releases"
2. Нажмите "Create a new release"
3. Заполните:
   - **Tag version**: `v1.0.0`
   - **Release title**: `RunQuest v1.0.0 - Initial Release`
   - **Description**: 
   ```
   ## 🎉 Initial Release of RunQuest
   
   ### Features
   - ✅ GPS tracking with high accuracy
   - ✅ Race system with predefined tracks
   - ✅ Gamification with levels, XP, and achievements
   - ✅ Social features with friends and activity feed
   - ✅ Complete REST API with Swagger documentation
   - ✅ Cross-platform Flutter app
   
   ### Technical Stack
   - Frontend: Flutter 3.3+, Dart
   - Backend: Django 4.2+, Django REST Framework
   - Database: PostgreSQL with PostGIS
   - Authentication: JWT tokens
   
   ### Documentation
   - Complete API documentation
   - Installation and setup guides
   - Architecture documentation
   - Contributing guidelines
   ```

### 2. Создание архива

Для демонстрации создайте архив проекта:
```bash
# Создайте архив (исключая .git и build файлы)
tar -czf RunQuest-v1.0.0.tar.gz --exclude='.git' --exclude='build' --exclude='__pycache__' .
```

## Настройка GitHub Pages (опционально)

### 1. Создание GitHub Pages

1. Перейдите в Settings → Pages
2. Выберите источник: "Deploy from a branch"
3. Выберите ветку: `main`
4. Выберите папку: `/ (root)`

### 2. Создание index.html

Создайте простую страницу для GitHub Pages:

```html
<!DOCTYPE html>
<html>
<head>
    <title>RunQuest - Running App Portfolio</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 40px; }
        .feature { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏃‍♂️ RunQuest</h1>
            <p>Full-stack running app with Flutter frontend and Django REST API backend</p>
        </div>
        
        <div class="feature">
            <h3>📱 Mobile App (Flutter)</h3>
            <p>Cross-platform mobile application with GPS tracking, interactive maps, and gamification features.</p>
        </div>
        
        <div class="feature">
            <h3>🖥️ Backend API (Django)</h3>
            <p>RESTful API with PostGIS integration for geospatial data processing and user management.</p>
        </div>
        
        <div class="feature">
            <h3>🎮 Gamification</h3>
            <p>Level system, achievements, challenges, and leaderboards to motivate users.</p>
        </div>
        
        <div class="feature">
            <h3>👥 Social Features</h3>
            <p>Friends system, activity feed, and joint runs for social interaction.</p>
        </div>
        
        <div class="feature">
            <h3>📚 Documentation</h3>
            <p>Complete documentation including API docs, architecture, and installation guides.</p>
        </div>
        
        <div class="feature">
            <h3>🔗 Links</h3>
            <p>
                <a href="https://github.com/YOUR_USERNAME/RunQuest">GitHub Repository</a> |
                <a href="https://github.com/YOUR_USERNAME/RunQuest/blob/main/README.md">Documentation</a> |
                <a href="https://github.com/YOUR_USERNAME/RunQuest/releases">Releases</a>
            </p>
        </div>
    </div>
</body>
</html>
```

## Добавление скриншотов

### 1. Подготовка скриншотов

1. Запустите приложение на эмуляторе или устройстве
2. Сделайте скриншоты всех основных экранов
3. Сохраните их в папку `screenshots/` с понятными именами

### 2. Обновление README

Добавьте секцию со скриншотами в README.md:

```markdown
## 📱 Screenshots

| Main Dashboard | GPS Tracking | Race Selection |
|----------------|--------------|----------------|
| ![Dashboard](screenshots/04_main_dashboard.png) | ![Tracking](screenshots/06_run_tracking.png) | ![Races](screenshots/07_race_selection.png) |

| Achievements | Social Feed | Profile |
|--------------|-------------|---------|
| ![Achievements](screenshots/09_achievements.png) | ![Feed](screenshots/12_activity_feed.png) | ![Profile](screenshots/13_profile_screen.png) |
```

## Финальная проверка

### 1. Проверка репозитория

- ✅ Все файлы загружены
- ✅ README.md отображается корректно
- ✅ Документация доступна
- ✅ Скриншоты добавлены
- ✅ Лицензия указана
- ✅ Topics добавлены

### 2. Проверка функциональности

- ✅ Проект можно клонировать
- ✅ Инструкции по установке работают
- ✅ Документация актуальна
- ✅ API документация доступна

## Продвижение проекта

### 1. Социальные сети

Поделитесь проектом в:
- LinkedIn
- Twitter
- Reddit (r/FlutterDev, r/django)
- Dev.to

### 2. Портфолио

Добавьте проект в:
- GitHub профиль (pinned repositories)
- LinkedIn портфолио
- Персональный сайт
- CV/резюме

### 3. Сообщество

- Участвуйте в обсуждениях
- Отвечайте на вопросы
- Принимайте feedback
- Вносите улучшения

## Поддержка проекта

### 1. Мониторинг

- Отслеживайте Issues
- Отвечайте на вопросы
- Принимайте Pull Requests
- Обновляйте документацию

### 2. Развитие

- Добавляйте новые функции
- Улучшайте производительность
- Обновляйте зависимости
- Создавайте новые релизы

---

**Поздравляем!** 🎉 Ваш проект RunQuest готов для демонстрации как портфолио на GitHub!
