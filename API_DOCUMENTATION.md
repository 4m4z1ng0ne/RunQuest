# RunQuest API Documentation

## Обзор

RunQuest API построен на Django REST Framework и предоставляет полный набор эндпоинтов для мобильного приложения. API использует JWT аутентификацию и поддерживает геопространственные данные через PostGIS.

## Базовый URL

```
http://localhost:8000/api/
```

## Аутентификация

API использует JWT (JSON Web Tokens) для аутентификации. Все защищенные эндпоинты требуют заголовок:

```
Authorization: Bearer <access_token>
```

### Получение токенов

**POST** `/api/token/`

Запрос:
```json
{
    "username": "your_username",
    "password": "your_password"
}
```

Ответ:
```json
{
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Обновление токена

**POST** `/api/token/refresh/`

Запрос:
```json
{
    "refresh": "your_refresh_token"
}
```

## Основные эндпоинты

### 1. Регистрация пользователя

**POST** `/api/register/`

Запрос:
```json
{
    "username": "new_user",
    "email": "user@example.com",
    "password": "secure_password",
    "password_confirm": "secure_password"
}
```

Ответ:
```json
{
    "user": {
        "id": 1,
        "username": "new_user",
        "email": "user@example.com"
    },
    "profile": {
        "id": 1,
        "level": 1,
        "experience_points": 0,
        "username": "new_user"
    },
    "tokens": {
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    }
}
```

### 2. Профиль пользователя

**GET** `/api/profile/`

Ответ:
```json
{
    "id": 1,
    "user": {
        "id": 1,
        "username": "user",
        "email": "user@example.com",
        "first_name": "",
        "last_name": ""
    },
    "avatar": "http://localhost:8000/media/avatars/avatar.jpg",
    "level": 5,
    "experience_points": 1250,
    "username": "user",
    "is_public": true,
    "show_runs": true,
    "show_achievements": true,
    "show_challenges": true,
    "show_statistics": true
}
```

**PUT** `/api/profile/`

Запрос:
```json
{
    "avatar": "base64_encoded_image",
    "username": "new_username",
    "is_public": false
}
```

### 3. Пробежки (Runs)

**GET** `/api/runs/`

Параметры запроса:
- `page` - номер страницы
- `page_size` - размер страницы
- `ordering` - сортировка (например: `-start_time`)

Ответ:
```json
{
    "count": 25,
    "next": "http://localhost:8000/api/runs/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "user": 1,
            "start_time": "2024-01-15T10:30:00Z",
            "end_time": "2024-01-15T11:00:00Z",
            "distance_meters": 5000.0,
            "duration_seconds": 1800,
            "calories_burned": 350,
            "route_data": {
                "type": "LineString",
                "coordinates": [[37.7749, -122.4194], [37.7849, -122.4094]]
            },
            "xp_earned": 50
        }
    ]
}
```

**POST** `/api/runs/`

Запрос:
```json
{
    "start_time": "2024-01-15T10:30:00Z",
    "end_time": "2024-01-15T11:00:00Z",
    "distance_meters": 5000.0,
    "duration_seconds": 1800,
    "calories_burned": 350,
    "route_data": {
        "type": "LineString",
        "coordinates": [[37.7749, -122.4194], [37.7849, -122.4094]]
    }
}
```

### 4. Гонки (Race Tracks)

**GET** `/api/race-tracks/`

Ответ:
```json
{
    "count": 10,
    "results": [
        {
            "id": 1,
            "name": "Центральный парк",
            "description": "Классическая трасса по Центральному парку",
            "distance_meters": 5000.0,
            "route_definition": {
                "type": "LineString",
                "coordinates": [[37.7749, -122.4194], [37.7849, -122.4094]]
            },
            "record_time_seconds": 1200,
            "record_holder": "fast_runner",
            "base_xp_reward": 100,
            "difficulty_level": "medium"
        }
    ]
}
```

**GET** `/api/race-tracks/{track_id}/leaderboard/`

Ответ:
```json
{
    "track": {
        "id": 1,
        "name": "Центральный парк"
    },
    "leaderboard": [
        {
            "rank": 1,
            "user": "fast_runner",
            "completion_time_seconds": 1200,
            "completion_date": "2024-01-10T10:30:00Z"
        }
    ]
}
```

### 5. Попытки гонок (User Race Attempts)

**GET** `/api/user-race-attempts/`

**POST** `/api/user-race-attempts/start_race/`

Запрос:
```json
{
    "race_track": 1
}
```

**POST** `/api/user-race-attempts/{attempt_id}/finish_race/`

Запрос:
```json
{
    "actual_route_data": {
        "type": "LineString",
        "coordinates": [[37.7749, -122.4194], [37.7849, -122.4094]]
    }
}
```

**GET** `/api/user-race-attempts/{attempt_id}/compare_route/`

Ответ:
```json
{
    "route_coverage_percentage": 85.5,
    "actual_distance_meters": 4800.0,
    "expected_distance_meters": 5000.0,
    "is_valid_attempt": true
}
```

### 6. Достижения (Achievements)

**GET** `/api/achievements/`

Ответ:
```json
{
    "count": 20,
    "results": [
        {
            "id": 1,
            "name": "Первый километр",
            "description": "Пробежать первый километр",
            "achievement_type": "distance",
            "target_value": 1000.0,
            "unit": "meters",
            "xp_reward": 50,
            "icon": "http://localhost:8000/media/achievement_icons/first_km.png",
            "is_secret": false
        }
    ]
}
```

**GET** `/api/user-achievements/`

Ответ:
```json
{
    "count": 5,
    "results": [
        {
            "id": 1,
            "achievement": {
                "id": 1,
                "name": "Первый километр",
                "description": "Пробежать первый километр",
                "xp_reward": 50
            },
            "earned_date": "2024-01-15T10:30:00Z",
            "xp_earned": 50
        }
    ]
}
```

### 7. Челленджи (Challenges)

**GET** `/api/challenges/`

Ответ:
```json
{
    "count": 5,
    "results": [
        {
            "id": 1,
            "name": "Недельный марафон",
            "description": "Пробежать 50 км за неделю",
            "challenge_type": "distance_goal",
            "target_value": 50000.0,
            "unit": "meters",
            "start_date": "2024-01-15T00:00:00Z",
            "end_date": "2024-01-22T23:59:59Z",
            "is_competitive": true,
            "xp_reward": 200,
            "is_active": true
        }
    ]
}
```

**GET** `/api/user-challenges/`

Ответ:
```json
{
    "count": 3,
    "results": [
        {
            "id": 1,
            "challenge": {
                "id": 1,
                "name": "Недельный марафон",
                "description": "Пробежать 50 км за неделю",
                "target_value": 50000.0,
                "unit": "meters"
            },
            "progress_value": 25000.0,
            "progress_percentage": 50.0,
            "is_completed": false,
            "completion_date": null
        }
    ]
}
```

### 8. Друзья (Friends)

**GET** `/api/friends/my_friends/`

Ответ:
```json
{
    "count": 5,
    "results": [
        {
            "id": 1,
            "friend": {
                "id": 2,
                "username": "friend_user",
                "profile": {
                    "level": 3,
                    "avatar": "http://localhost:8000/media/avatars/friend.jpg"
                }
            },
            "status": "accepted",
            "created_at": "2024-01-10T10:30:00Z"
        }
    ]
}
```

**GET** `/api/friends/pending_requests/`

**POST** `/api/friends/`

Запрос:
```json
{
    "friend": 2
}
```

**POST** `/api/friends/{friend_id}/accept/`

**POST** `/api/friends/{friend_id}/reject/`

### 9. Лента активности (Activity Feed)

**GET** `/api/activity-feed/`

Параметры запроса:
- `page` - номер страницы
- `page_size` - размер страницы

Ответ:
```json
{
    "count": 50,
    "next": "http://localhost:8000/api/activity-feed/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "activity_type": "run_completed",
            "user": {
                "id": 1,
                "username": "user",
                "profile": {
                    "avatar": "http://localhost:8000/media/avatars/user.jpg"
                }
            },
            "timestamp": "2024-01-15T10:30:00Z",
            "description": "Пользователь завершил пробежку на 5.0 км",
            "related_run": {
                "id": 1,
                "distance_meters": 5000.0,
                "duration_seconds": 1800
            }
        }
    ]
}
```

## Коды ошибок

- `400` - Неверный запрос
- `401` - Не авторизован
- `403` - Доступ запрещен
- `404` - Ресурс не найден
- `500` - Внутренняя ошибка сервера

## Пагинация

Большинство списков поддерживают пагинацию:

```
GET /api/runs/?page=2&page_size=20
```

## Фильтрация и сортировка

Многие эндпоинты поддерживают фильтрацию и сортировку:

```
GET /api/runs/?ordering=-start_time&distance_meters__gte=1000
```

## Геопространственные данные

API использует GeoJSON формат для геопространственных данных:

```json
{
    "type": "LineString",
    "coordinates": [
        [longitude, latitude],
        [longitude, latitude]
    ]
}
```

## Rate Limiting

API имеет ограничения на количество запросов:
- 1000 запросов в час для аутентифицированных пользователей
- 100 запросов в час для неаутентифицированных пользователей
