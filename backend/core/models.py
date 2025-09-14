from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.gis.db import models as gismodels
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from shapely.geometry import LineString
from django.contrib.gis.db.models.functions import Length # Import Length function

# Выбор статуса запроса в друзья
FRIEND_REQUEST_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('accepted', 'Accepted'),
    ('rejected', 'Rejected'),
]

# Выбор типа челленджа
CHALLENGE_TYPE_CHOICES = [
    ('distance', 'Distance'),
    ('duration', 'Duration'),
    ('count', 'Run Count'),
]

# Профиль пользователя с аватаром
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    level = models.IntegerField(default=1)
    experience_points = models.IntegerField(default=0)
    username = models.CharField(max_length=100, unique=True, blank=True, null=True)
    # Можно добавить другие поля (например, bio, город и т.д.)

    # Настройки приватности
    is_public = models.BooleanField(default=True) # Весь профиль публичный или только для друзей
    show_runs = models.BooleanField(default=True) # Показывать пробежки (если не публичный, то друзьям?)
    show_achievements = models.BooleanField(default=True) # Показывать достижения
    show_challenges = models.BooleanField(default=True) # Показывать челленджи
    show_statistics = models.BooleanField(default=True) # Показывать общую статистику
    # Добавьте другие настройки приватности по необходимости (например, показывать статистику, гонки и т.д.)

    def __str__(self):
        return f'Profile of {self.user.username}'

# Достижения
class Achievement(models.Model):
    ACHIEVEMENT_TYPES = [
        ('distance', 'Distance'),
        ('duration', 'Duration'),
        ('run_count', 'Run Count'),
        ('race_count', 'Race Count'),
        ('specific_route', 'Specific Route'),
        # Добавьте другие типы достижений
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    achievement_type = models.CharField(max_length=50, choices=ACHIEVEMENT_TYPES, default='run_count')
    target_value = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    xp_reward = models.IntegerField()
    icon = models.ImageField(upload_to='achievement_icons/', null=True, blank=True)
    is_secret = models.BooleanField(default=False, verbose_name="Секретное достижение")

    # Поле для связи с RaceTrack, если достижение связано с определенной трассой
    related_racetrack = models.ForeignKey('RaceTrack', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name

# Челленджи
class Challenge(models.Model):
    CHALLENGE_TYPES = [
        ('distance_goal', 'Distance Goal'),
        ('duration_goal', 'Duration Goal'),
        ('run_count_goal', 'Run Count Goal'),
        ('complete_racetrack', 'Complete Racetrack'),
        # Добавьте другие типы челленджей
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    challenge_type = models.CharField(max_length=50, choices=CHALLENGE_TYPES, default='distance_goal')
    target_value = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_competitive = models.BooleanField(default=False)
    # Поле для связи с RaceTrack, если челлендж связан с определенной трассой
    related_racetrack = models.ForeignKey('RaceTrack', on_delete=models.SET_NULL, null=True, blank=True)
    xp_reward = models.IntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

# Трек гонки
class RaceTrack(models.Model):
    name = models.CharField(max_length=255)
    route_definition = gismodels.LineStringField(geography=True)
    record_time_seconds = models.IntegerField(null=True, blank=True)
    length_meters = models.FloatField(null=True, blank=True)
    
    # Поля для настройки расчета XP
    base_xp_reward = models.IntegerField(default=100) # Базовое количество XP за прохождение
    xp_penalty_per_second = models.FloatField(default=2.0) # Штраф XP за каждую секунду сверх рекорда
    route_match_xp_multiplier = models.FloatField(default=1.0) # Множитель XP от совпадения маршрута (1.0 = 100%)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # Сначала сохраняем, чтобы получить PK для нового объекта
        if self.route_definition:
            try:
                track_with_length = RaceTrack.objects.filter(pk=self.pk).annotate(
                    calculated_length=Length('route_definition')
                ).first()
                if track_with_length and track_with_length.calculated_length:
                    self.length_meters = track_with_length.calculated_length.m
                else:
                    self.length_meters = None
            except Exception as e:
                print(f"Error calculating length with Length(): {e}")
                self.length_meters = None
            # Сохраняем ещё раз, если длина изменилась
            super().save(update_fields=['length_meters'])
        else:
            self.length_meters = None
            super().save(update_fields=['length_meters'])

    def __str__(self):
        return self.name

# Пробежка
class Run(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='runs')
    start_time = models.DateTimeField(auto_now_add=True)
    distance_meters = models.FloatField(null=True, blank=True)
    route_data = gismodels.LineStringField(null=True, blank=True, geography=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    calories = models.IntegerField(null=True, blank=True)
    # Добавляем ссылку на запланированную совместную пробежку (если есть)
    # Add a link to a planned joint run (if any)
    planned_joint_run = models.ForeignKey('PlannedJointRun', on_delete=models.SET_NULL, null=True, blank=True, related_name='actual_runs')
    # New fields for run results
    xp_earned = models.IntegerField(default=0)
    earned_achievements = models.ManyToManyField('Achievement', related_name='runs_earned_in', blank=True)
    completed_challenges = models.ManyToManyField('Challenge', related_name='runs_completed_in', blank=True)

    def __str__(self):
        return f'Run by {self.user.username} on {self.start_time.strftime("%Y-%m-%d %H:%M")}'

# Попытка в гонке
class UserRaceAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='race_attempts')
    track = models.ForeignKey(RaceTrack, on_delete=models.CASCADE)
    duration_seconds = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=50, default='pending')
    xp_earned = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    actual_route_data = gismodels.LineStringField(null=True, blank=True, geography=True)
    actual_distance_meters = models.FloatField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    completion_time = models.DateTimeField(null=True, blank=True)
    earned_achievements = models.ManyToManyField('Achievement', related_name='race_attempts_earned_in', blank=True)
    completed_challenges = models.ManyToManyField('Challenge', related_name='race_attempts_completed_in', blank=True)

    def __str__(self):
        return f'{self.user.username} - {self.track.name} ({self.status})'

# Достижения пользователя
class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    received_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'achievement')

    def __str__(self):
        status = "Completed" if self.completed else "In Progress"
        return f'{self.user.username} - {self.achievement.name} ({status})'

# Челленджи пользователя
class UserChallenge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_challenges')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE)
    progress = models.FloatField(default=0.0)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    completion_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'challenge')

    def __str__(self):
        status = "Completed" if self.completed else f"{self.progress}/{self.challenge.target_value}"
        return f'{self.user.username} - {self.challenge.name} ({status})'

# Друзья (социальные связи)
class Friend(models.Model):
    from_user = models.ForeignKey(User, related_name='sent_requests', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='received_requests', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=FRIEND_REQUEST_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

    def __str__(self):
        return f"Friend request from {self.from_user.username} to {self.to_user.username} ({self.status})"

# Модель для элементов ленты активности
class ActivityItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_items')
    item_type = models.CharField(max_length=50) # Тип события (e.g., 'run_completed', 'achievement_unlocked', 'friend_request_accepted', 'level_up', 'race_ranked', 'joint_run_invitation_sent', 'joint_run_invitation_accepted', 'joint_run_invitation_rejected', 'joint_run_completed')
    created_at = models.DateTimeField(auto_now_add=True)

    # Добавляем опциональные внешние ключи к связанным объектам
    run = models.ForeignKey('Run', on_delete=models.SET_NULL, null=True, blank=True)
    user_achievement = models.ForeignKey('UserAchievement', on_delete=models.SET_NULL, null=True, blank=True)
    user_challenge = models.ForeignKey('UserChallenge', on_delete=models.SET_NULL, null=True, blank=True)
    friend_relationship = models.ForeignKey('Friend', on_delete=models.SET_NULL, null=True, blank=True)
    user_race_attempt = models.ForeignKey('UserRaceAttempt', on_delete=models.SET_NULL, null=True, blank=True)
    planned_joint_run = models.ForeignKey('PlannedJointRun', on_delete=models.SET_NULL, null=True, blank=True)
    joint_run_invitation = models.ForeignKey('JointRunInvitation', on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_items')
    is_published = models.BooleanField(default=True) # Field to control visibility

    # Новое поле для управления комментариями
    allow_comments = models.BooleanField(default=True) # Разрешены ли комментарии к этой записи

    # Новое поле для ссылки на пользователя, связанного с событием (например, добавленный участник)
    related_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='related_activity_items')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.item_type} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# Новая модель для приглашений на совместную пробежку
class JointRunInvitation(models.Model):
    INVITATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    sender = models.ForeignKey(User, related_name='sent_joint_run_invitations', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_joint_run_invitations', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=INVITATION_STATUS_CHOICES, default='pending')
    # Предлагаемое время пробежки
    suggested_time = models.DateTimeField(null=True, blank=True)
    # Предлагаемая трасса (опционально)
    suggested_racetrack = models.ForeignKey('RaceTrack', on_delete=models.SET_NULL, null=True, blank=True)
    # Новое поле для места встречи
    meeting_location = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('sender', 'recipient', 'created_at') # Уникальность для предотвращения дубликатов, включая время создания

    def __str__(self):
        return f"Joint run invitation from {self.sender.username} to {self.recipient.username} ({self.status})"

# Новая модель для запланированных совместных пробежек (после принятия приглашения)
class PlannedJointRun(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Ссылка на принятое приглашение
    invitation = models.OneToOneField('JointRunInvitation', on_delete=models.CASCADE, related_name='planned_run')
    # Участники совместной пробежки (отправитель и получатель)
    participants = models.ManyToManyField(User, related_name='planned_joint_runs')
    # Предлагаемое время из приглашения
    suggested_time = models.DateTimeField(null=True, blank=True)
    # Предлагаемая трасса из приглашения
    suggested_racetrack = models.ForeignKey('RaceTrack', on_delete=models.SET_NULL, null=True, blank=True)
    # Место встречи из приглашения
    meeting_location = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='planned')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Фактическое время старта совместной пробежки
    actual_start_time = models.DateTimeField(null=True, blank=True)

    # Возможно, позже добавим поля для ссылок на фактические объекты Run, когда пробежка будет завершена
    # sender_run = models.ForeignKey('Run', on_delete=models.SET_NULL, null=True, blank=True, related_name='planned_runs_as_sender')
    # recipient_run = models.ForeignKey('Run', on_delete=models.SET_NULL, null=True, blank=True, related_name='planned_runs_as_recipient')

    def __str__(self):
        participant_names = ', '.join([user.username for user in self.participants.all()])
        return f"Planned Joint Run for {participant_names} ({self.status})"

# Модель для комментариев к элементам ленты активности
class ActivityComment(models.Model):
    # Ссылка на элемент ленты активности
    activity_item = models.ForeignKey('ActivityItem', on_delete=models.CASCADE, related_name='comments')
    # Пользователь, оставивший комментарий
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_comments')
    # Текст комментария
    text = models.TextField()
    # Время создания комментария
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at'] # Комментарии сортируются по времени создания

    def __str__(self):
        return f'Comment by {self.user.username} on ActivityItem {self.activity_item.id} at {self.created_at.strftime("%Y-%m-%d %H:%M")}'

# Новая модель для блокировки пользователей
class Block(models.Model):
    # Пользователь, который блокирует
    blocker = models.ForeignKey(User, related_name='blocking', on_delete=models.CASCADE)
    # Пользователь, которого блокируют
    blocked = models.ForeignKey(User, related_name='blocked_by', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked') # Один пользователь не может заблокировать другого более одного раза

    def __str__(self):
        return f'{self.blocker.username} blocked {self.blocked.username}'

# Новая модель для хранения токенов устройств для пуш-уведомлений
class DeviceToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_tokens')
    # Токен устройства, уникален для каждого устройства
    token = models.CharField(max_length=255, unique=True)
    # Тип устройства (например, 'android', 'ios')
    # Device type (e.g., 'android', 'ios')
    device_type = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Возможно, уникальность должна быть по паре user + token, если у одного пользователя несколько устройств
        unique_together = ('user', 'token') # Убедиться, что у одного пользователя один токен уникален (на всякий случай)

    def __str__(self):
        return f'{self.user.username} - {self.device_type} - {self.token[:10]}...'

# Сигнал для автоматического создания профиля при создании пользователя
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Этот сигнал можно использовать для сохранения профиля при обновлении пользователя
    pass # Не делаем ничего по умолчанию, профиль сохраняется отдельно

class SuggestedRoute(models.Model):
    STATUS_CHOICES = [
        ('pending', 'На модерации'),
        ('approved', 'Принят'),
        ('rejected', 'Отклонён'),
    ]
    name = models.CharField('Название маршрута', max_length=255)
    description = models.TextField('Описание')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    route_points = models.JSONField('Координаты маршрута')  # Список точек маршрута
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    def __str__(self):
        return self.name
