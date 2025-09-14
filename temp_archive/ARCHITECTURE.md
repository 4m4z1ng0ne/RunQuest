# RunQuest Architecture Documentation

## Обзор архитектуры

RunQuest построен по принципу клиент-серверной архитектуры с разделением на frontend (мобильное приложение) и backend (API сервер). Приложение использует современные технологии для обеспечения высокой производительности, масштабируемости и удобства разработки.

## Диаграмма архитектуры

```
┌─────────────────┐    HTTP/HTTPS    ┌─────────────────┐
│                 │    REST API      │                 │
│   Flutter App   │◄─────────────────┤  Django Backend │
│   (Frontend)    │                  │   (Backend)     │
│                 │                  │                 │
└─────────────────┘                  └─────────────────┘
         │                                     │
         │                                     │
         ▼                                     ▼
┌─────────────────┐                  ┌─────────────────┐
│   Device GPS    │                  │   PostgreSQL    │
│   & Sensors     │                  │   + PostGIS     │
└─────────────────┘                  └─────────────────┘
```

## Frontend Architecture (Flutter)

### Структура приложения

```
frontend/lib/
├── main.dart                 # Точка входа приложения
├── models/                   # Модели данных
│   ├── user.dart
│   ├── challenge.dart
│   └── ...
├── screens/                  # Экраны приложения
│   ├── auth/                 # Аутентификация
│   ├── main/                 # Основные экраны
│   └── tabs/                 # Табы навигации
├── services/                 # API сервисы
│   ├── auth_service.dart
│   ├── friend_service.dart
│   └── ...
└── widgets/                  # Переиспользуемые виджеты
```

### Ключевые компоненты

#### 1. State Management
- **Provider** - для управления состоянием приложения
- **AuthService** - синглтон для управления аутентификацией
- **SharedPreferences** - для локального хранения данных

#### 2. Navigation
- **MaterialApp** - корневой виджет навигации
- **TabBar** - для переключения между основными разделами
- **Navigator** - для навигации между экранами

#### 3. Maps & Location
- **flutter_map** - для отображения карт
- **geolocator** - для работы с GPS
- **latlong2** - для работы с координатами

#### 4. Network Layer
- **Dio** - HTTP клиент для API запросов
- **JWT Decoder** - для работы с JWT токенами
- **Secure Storage** - для безопасного хранения токенов

### Паттерны проектирования

#### 1. Service Layer Pattern
```dart
class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  
  Future<bool> login(String username, String password) async {
    // Логика аутентификации
  }
}
```

#### 2. Repository Pattern
```dart
class UserRepository {
  final ApiService _apiService;
  
  Future<User> getUserProfile() async {
    return await _apiService.get('/api/profile/');
  }
}
```

#### 3. Provider Pattern
```dart
class UserProvider extends ChangeNotifier {
  User? _user;
  User? get user => _user;
  
  void updateUser(User user) {
    _user = user;
    notifyListeners();
  }
}
```

## Backend Architecture (Django)

### Структура проекта

```
backend/
├── backend/                  # Настройки Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                     # Основное приложение
│   ├── models.py            # Модели данных
│   ├── views.py             # API представления
│   ├── serializers.py       # Сериализаторы
│   ├── urls.py              # URL маршруты
│   └── utils.py             # Утилиты
└── manage.py                # Django CLI
```

### Архитектурные слои

#### 1. Model Layer (Django ORM)
```python
class Run(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    route_data = gismodels.LineStringField(geography=True)
    
    def calculate_distance(self):
        return self.route_data.length
```

#### 2. Serializer Layer (DRF)
```python
class RunSerializer(serializers.ModelSerializer):
    class Meta:
        model = Run
        fields = '__all__'
        
    def create(self, validated_data):
        # Кастомная логика создания
        return super().create(validated_data)
```

#### 3. View Layer (ViewSets)
```python
class RunViewSet(viewsets.ModelViewSet):
    queryset = Run.objects.all()
    serializer_class = RunSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
```

#### 4. URL Layer (Routers)
```python
router = routers.DefaultRouter()
router.register(r'runs', RunViewSet)
router.register(r'race-tracks', RaceTrackViewSet)
```

### Ключевые компоненты

#### 1. Authentication & Authorization
- **JWT Tokens** - для аутентификации
- **Custom Permissions** - для контроля доступа
- **User Profiles** - расширенная модель пользователя

#### 2. Database Layer
- **PostgreSQL** - основная база данных
- **PostGIS** - геопространственные расширения
- **GeoDjango** - интеграция с Django

#### 3. API Layer
- **Django REST Framework** - API фреймворк
- **ViewSets** - для CRUD операций
- **Serializers** - для сериализации данных
- **Routers** - для автоматической маршрутизации

#### 4. GIS Integration
```python
from django.contrib.gis.db import models as gismodels
from django.contrib.gis.db.models.functions import Length

class RaceTrack(models.Model):
    route_definition = gismodels.LineStringField(geography=True)
    
    def calculate_length(self):
        return RaceTrack.objects.annotate(
            length=Length('route_definition')
        ).get(id=self.id).length
```

## Database Schema

### Основные таблицы

#### 1. Users & Profiles
```sql
-- Django auth_user (стандартная таблица)
auth_user (id, username, email, password, ...)

-- Расширенный профиль
core_profile (
    id, user_id, avatar, level, experience_points,
    username, is_public, show_runs, show_achievements
)
```

#### 2. Runs & Activities
```sql
core_run (
    id, user_id, start_time, end_time, distance_meters,
    duration_seconds, calories_burned, route_data (LineString),
    xp_earned
)
```

#### 3. Race System
```sql
core_racetrack (
    id, name, description, distance_meters,
    route_definition (LineString), record_time_seconds,
    record_holder_id, base_xp_reward, difficulty_level
)

core_userraceattempt (
    id, user_id, race_track_id, start_time, end_time,
    completion_time_seconds, status, xp_earned,
    actual_route_data (LineString), actual_distance_meters
)
```

#### 4. Gamification
```sql
core_achievement (
    id, name, description, achievement_type,
    target_value, unit, xp_reward, icon, is_secret
)

core_challenge (
    id, name, description, challenge_type,
    target_value, unit, start_date, end_date,
    is_competitive, xp_reward, is_active
)
```

#### 5. Social Features
```sql
core_friend (
    id, user_id, friend_id, status, created_at
)

core_activityitem (
    id, activity_type, user_id, timestamp,
    description, related_run_id, related_achievement_id
)
```

## Data Flow

### 1. User Registration Flow
```
Flutter App → POST /api/register/ → Django Backend
    ↓
Create User & Profile → Generate JWT → Return Tokens
    ↓
Store Tokens in Secure Storage → Navigate to Main App
```

### 2. Run Tracking Flow
```
GPS Location Updates → Flutter App → Build Route Data
    ↓
POST /api/runs/ → Django Backend → Validate & Save
    ↓
Calculate XP → Update User Level → Check Achievements
    ↓
Create Activity Item → Return Response
```

### 3. Race Participation Flow
```
Select Race Track → POST /api/user-race-attempts/start_race/
    ↓
Create Race Attempt → Start GPS Tracking
    ↓
Finish Race → POST /api/user-race-attempts/{id}/finish_race/
    ↓
Compare Routes → Calculate Results → Update Leaderboard
```

## Security Considerations

### 1. Authentication
- **JWT Tokens** с коротким временем жизни
- **Refresh Tokens** для обновления доступа
- **Secure Storage** на клиенте

### 2. Data Protection
- **HTTPS** для всех API запросов
- **CORS** настройки для безопасности
- **Input Validation** на всех эндпоинтах

### 3. Privacy
- **Profile Settings** для контроля видимости
- **Friend System** для ограничения доступа
- **Data Encryption** для чувствительных данных

## Performance Optimizations

### 1. Database
- **Indexes** на часто используемые поля
- **Query Optimization** с select_related/prefetch_related
- **Connection Pooling** для PostgreSQL

### 2. API
- **Pagination** для больших списков
- **Caching** для статических данных
- **Compression** для ответов API

### 3. Frontend
- **Lazy Loading** для изображений
- **State Management** для оптимизации рендеринга
- **Offline Support** для базовой функциональности

## Scalability Considerations

### 1. Horizontal Scaling
- **Load Balancers** для распределения нагрузки
- **Database Replication** для чтения
- **CDN** для статических файлов

### 2. Microservices Potential
- **User Service** - управление пользователями
- **Activity Service** - пробежки и активность
- **Social Service** - друзья и социальные функции
- **Gamification Service** - достижения и челленджи

### 3. Caching Strategy
- **Redis** для сессий и кеширования
- **Database Query Caching**
- **API Response Caching**

## Deployment Architecture

### Development Environment
```
Local Machine:
├── Flutter App (Debug Mode)
├── Django Dev Server
└── PostgreSQL (Local)
```

### Production Environment
```
Cloud Infrastructure:
├── Mobile App (App Store/Play Store)
├── Load Balancer
├── Django App Servers (Multiple)
├── PostgreSQL Cluster
├── Redis Cache
└── CDN for Static Files
```

## Monitoring & Logging

### 1. Application Monitoring
- **Error Tracking** (Sentry)
- **Performance Monitoring** (APM)
- **User Analytics** (Firebase Analytics)

### 2. Infrastructure Monitoring
- **Server Metrics** (CPU, Memory, Disk)
- **Database Performance**
- **API Response Times**

### 3. Logging Strategy
- **Structured Logging** (JSON format)
- **Log Aggregation** (ELK Stack)
- **Alert System** для критических ошибок

## Future Enhancements

### 1. Real-time Features
- **WebSocket** для live tracking
- **Push Notifications** для социальных событий
- **Real-time Leaderboards**

### 2. Advanced Analytics
- **Machine Learning** для рекомендаций
- **Predictive Analytics** для тренировок
- **Health Insights** на основе данных

### 3. Integration Opportunities
- **Wearable Devices** (Apple Watch, Fitbit)
- **Health Apps** (Apple Health, Google Fit)
- **Social Platforms** (Strava, Nike Run Club)
