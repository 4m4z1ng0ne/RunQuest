from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile, Run, Achievement, Challenge, UserAchievement, UserChallenge, RaceTrack, UserRaceAttempt, Friend, ActivityItem, JointRunInvitation, PlannedJointRun, ActivityComment, Block, DeviceToken, SuggestedRoute
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from django.contrib.gis.geos import LineString # Импортируем LineString
from django.db.models import Q, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from django.utils import timezone
from django.db import transaction
from django.db.models import F # Импортируем F object для обновления рекорда
from .utils import calculate_xp_for_run, check_and_award_achievements, check_and_update_challenges, check_for_race_record_broken, update_user_profile_xp_and_level # Import utility functions

# Сериализаторы для геймификации
# Serializers for gamification
class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = ('id', 'name', 'description', 'xp_reward', 'icon', 'is_secret')

class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ['id', 'name', 'description', 'challenge_type', 'target_value', 'unit', 'start_date', 'end_date', 'is_competitive', 'related_racetrack', 'xp_reward', 'is_active']

class PublicUserSerializer(serializers.ModelSerializer):
    level = serializers.IntegerField(source='profile.level', read_only=True)
    experience_points = serializers.IntegerField(source='profile.experience_points', read_only=True)
    is_public = serializers.BooleanField(source='profile.is_public', read_only=True)
    show_runs = serializers.BooleanField(source='profile.show_runs', read_only=True)
    show_achievements = serializers.BooleanField(source='profile.show_achievements', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'level', 'experience_points', 'is_public', 'show_runs', 'show_achievements']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с таким именем пользователя уже существует.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    # поле для отображения последних записей активности
    recent_activity_items = serializers.SerializerMethodField()
    # поле для отображения статистики
    statistics = serializers.SerializerMethodField()
    # поле для отображения списка друзей
    friends_list = serializers.SerializerMethodField()
    # поле для индикации статуса блокировки
    is_blocked_by_viewer = serializers.SerializerMethodField()
    viewer_is_blocked = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ('id', 'username', 'email', 'avatar', 'level', 'experience_points',
                  'is_public', 'show_runs', 'show_achievements', 'show_challenges',
                  'recent_activity_items', 'show_statistics', 'statistics', 'friends_list',
                  'user_id', 'is_blocked_by_viewer', 'viewer_is_blocked') # Добавьте новые поля
        read_only_fields = ('id', 'username', 'email', 'level', 'experience_points', 'user_id')

    def _is_owner_or_friend_or_public(self, obj, request_user):
        is_owner = request_user == obj.user
        is_friend = False
        if request_user.is_authenticated and not is_owner:
            is_friend = Friend.objects.filter(
                Q(from_user=request_user, to_user=obj.user, status='accepted') |
                Q(from_user=obj.user, to_user=request_user, status='accepted')
            ).exists()
        return is_owner or is_friend or obj.is_public

    def _is_blocked(self, request_user, profile_owner):
        if not request_user.is_authenticated:
            return False
        # Check if request_user is blocked by profile_owner
        if Block.objects.filter(blocker=profile_owner, blocked=request_user).exists():
            return True
        # Check if profile_owner is blocked by request_user
        if Block.objects.filter(blocker=request_user, blocked=profile_owner).exists():
            return True
        return False

    def get_recent_activity_items(self, obj):
        profile_owner = obj.user
        request_user = self.context['request'].user
        is_owner = request_user == profile_owner

        if is_owner or (self._is_owner_or_friend_or_public(obj, request_user) and (obj.show_runs or obj.show_achievements or obj.show_challenges)):
            activity_items = ActivityItem.objects.filter(user=profile_owner)
            if not is_owner:
                 activity_items = activity_items.filter(is_published=True)
            recent_items = activity_items.order_by('-created_at')[:10]
            serializer = ActivityItemSerializer(recent_items, many=True, context=self.context)
            return serializer.data
        return None # Return None if not authorized to see activity

    def get_statistics(self, obj):
        profile_owner = obj.user
        request_user = self.context['request'].user
        is_owner = request_user == profile_owner

        if is_owner or (self._is_owner_or_friend_or_public(obj, request_user) and obj.show_statistics):
            total_runs = Run.objects.filter(user=profile_owner).count()
            total_distance_meters = Run.objects.filter(user=profile_owner).aggregate(total_distance=Sum('distance_meters'))['total_distance'] or 0
            total_duration_seconds = Run.objects.filter(user=profile_owner).aggregate(total_duration=Sum('duration_seconds'))['total_duration'] or 0
            total_xp_earned = profile_owner.profile.experience_points
            completed_challenges_count = UserChallenge.objects.filter(user=profile_owner, completed=True).count()
            achievements_count = UserAchievement.objects.filter(user=profile_owner).count()

            statistics_data = {
                'total_runs': total_runs,
                'total_distance_km': round(total_distance_meters / 1000, 2),
                'total_duration_hours': round(total_duration_seconds / 3600, 2),
                'total_xp_earned': total_xp_earned,
                'completed_challenges_count': completed_challenges_count,
                'achievements_count': achievements_count,
            }
            return statistics_data
        return None # Return None if not authorized to see statistics

    def get_friends_list(self, obj):
        profile_owner = obj.user
        request_user = self.context['request'].user
        is_owner = request_user == profile_owner

        if is_owner or self._is_owner_or_friend_or_public(obj, request_user):
            friends = Friend.objects.filter(Q(from_user=profile_owner, status='accepted') | Q(to_user=profile_owner, status='accepted')).distinct()
            # If the requesting user is not the owner, filter the friends list to only show mutual friends or public profiles
            if not is_owner:
                 friends = friends.filter(
                     Q(from_user__profile__is_public=True) | Q(to_user__profile__is_public=True) |
                     Q(from_user__in=Friend.objects.filter(to_user=request_user, status='accepted').values('from_user')) |
                     Q(to_user__in=Friend.objects.filter(from_user=request_user, status='accepted').values('to_user'))
                 ).exclude(Q(from_user=request_user) | Q(to_user=request_user))

            # Сериализуем объекты User, а не только их имена пользователей
            # Serialize User objects, not just their usernames
            serialized_friends = []
            for f in friends:
                friend_user = f.to_user if f.from_user == profile_owner else f.from_user
                serialized_friends.append(PublicUserSerializer(friend_user, context=self.context).data)
            return serialized_friends
        return None # Return None if not authorized to see friends list

    def get_is_blocked_by_viewer(self, obj):
        request_user = self.context['request'].user
        if request_user.is_authenticated and request_user != obj.user:
            return Block.objects.filter(blocker=request_user, blocked=obj.user).exists()
        return False

    def get_viewer_is_blocked(self, obj):
        request_user = self.context['request'].user
        if request_user.is_authenticated and request_user != obj.user:
            return Block.objects.filter(blocker=obj.user, blocked=request_user).exists()
        return False

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request_user = self.context['request'].user
        profile_owner = instance.user
        is_owner = request_user == profile_owner
        is_friend = False
        if request_user.is_authenticated and not is_owner:
             is_friend = Friend.objects.filter(
                 Q(from_user=request_user, to_user=profile_owner, status='accepted') |
                 Q(from_user=profile_owner, to_user=request_user, status='accepted')
             ).exists()

        is_blocked_relationship_by_viewer = self.get_is_blocked_by_viewer(instance) # Используем новый метод
        viewer_is_blocked_by_profile_owner = self.get_viewer_is_blocked(instance) # Используем новый метод

        # Если текущий пользователь или владелец профиля заблокировали друг друга,
        # или профиль не публичный и нет дружбы, то показываем минимальную информацию.
        if (viewer_is_blocked_by_profile_owner or is_blocked_relationship_by_viewer) or \
           (not is_owner and not (is_friend or instance.is_public)):
            minimal_representation = {
                'id': representation.get('id'),
                'username': representation.get('username'),
                'user_id': representation.get('user_id'),
                'avatar': representation.get('avatar'),
                'profile_access_denied': True,
                'is_blocked_by_viewer': is_blocked_relationship_by_viewer, # Добавляем статус блокировки
                'viewer_is_blocked': viewer_is_blocked_by_profile_owner,     # Добавляем статус блокировки
                'message': "Эта страница закрыта",
                'can_send_friend_request': (
                    request_user.is_authenticated and
                    not is_owner and
                    not is_friend and
                    not is_blocked_relationship_by_viewer and # Проверяем, что не заблокировано
                    not viewer_is_blocked_by_profile_owner and # Проверяем, что нас не заблокировали
                    not Friend.objects.filter(
                        Q(from_user=request_user, to_user=profile_owner, status='pending') |
                        Q(from_user=profile_owner, to_user=request_user, status='pending')
                    ).exists()
                )
            }
            return minimal_representation
        else:
            # Если владелец, друг или публичный профиль, применяем существующую условную логику
            representation['profile_access_denied'] = False
            representation['can_send_friend_request'] = False # Неактуально, если доступ не запрещен

            if not is_owner:
                if not (is_friend and instance.show_statistics) and not (instance.is_public and instance.show_statistics):
                    representation.pop('level', None)
                    representation.pop('experience_points', None)
                    representation.pop('statistics', None)

                if not (is_friend and (instance.show_runs or instance.show_achievements or instance.show_challenges)) and not (instance.is_public and (instance.show_runs or instance.show_achievements or instance.show_challenges)):
                    representation.pop('recent_activity_items', None)
                    representation.pop('show_runs', None)
                    representation.pop('show_achievements', None)
                    representation.pop('show_challenges', None)

                if not (is_friend or instance.is_public):
                    representation.pop('friends_list', None)
            
            return representation

# Сериализатор для модели Run с учетом GeoDjango
# Serializer for the Run model with GeoDjango support
class RunSerializer(GeoFeatureModelSerializer):
    earned_achievements = AchievementSerializer(many=True, read_only=True)
    completed_challenges = ChallengeSerializer(many=True, read_only=True)

    class Meta:
        model = Run
        geo_field = 'route_data'
        fields = (
            'id',
            'user',
            'start_time',
            'distance_meters',
            'route_data',
            'duration_seconds',
            'calories',
            'planned_joint_run',
            'xp_earned',
            'earned_achievements',
            'completed_challenges',
        )
        read_only_fields = ('user', 'start_time')

class UserAchievementSerializer(serializers.ModelSerializer):
    achievement_name = serializers.CharField(source='achievement.name', read_only=True)
    achievement_description = serializers.CharField(source='achievement.description', read_only=True)
    achievement_xp_reward = serializers.IntegerField(source='achievement.xp_reward', read_only=True)
    achievement_icon = serializers.ImageField(source='achievement.icon', read_only=True)

    class Meta:
        model = UserAchievement
        fields = ('id', 'user', 'achievement', 'achievement_name', 'achievement_description', 'achievement_xp_reward', 'achievement_icon', 'received_at', 'completed', 'completion_date')
        read_only_fields = ('id', 'user', 'achievement', 'achievement_name', 'achievement_description', 'achievement_xp_reward', 'achievement_icon', 'received_at', 'completed', 'completion_date')

class UserChallengeSerializer(serializers.ModelSerializer):
    challenge = ChallengeSerializer(read_only=True)

    class Meta:
        model = UserChallenge
        fields = ['id', 'user', 'challenge', 'progress', 'completed', 'updated_at', 'completion_date']

# Сериализатор для гонок на время
# Serializers for timed races
class RaceTrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = RaceTrack
        fields = ('id', 'name', 'length_meters', 'route_definition', 'record_time_seconds') # Changed distance_meters to distance
        read_only_fields = ('id', 'record_time_seconds') # Рекорд обновляется логикой сервера
        # Record is updated by server logic

class UserRaceAttemptSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)
    race_track_name = serializers.CharField(source='track.name', read_only=True)
    earned_achievements = AchievementSerializer(many=True, read_only=True)
    completed_challenges = ChallengeSerializer(many=True, read_only=True)
    is_record_broken = serializers.SerializerMethodField()
    base_xp = serializers.SerializerMethodField()
    record_bonus_xp = serializers.SerializerMethodField()
    achievements_xp = serializers.SerializerMethodField()
    challenges_xp = serializers.SerializerMethodField()

    class Meta:
        model = UserRaceAttempt
        fields = ['id', 'track', 'user', 'race_track_name',
                  'duration_seconds', 'status', 'xp_earned',
                  'actual_route_data', 'actual_distance_meters', 'start_time',
                  'earned_achievements',
                  'completed_challenges',
                  'is_record_broken',
                  'base_xp', 'record_bonus_xp', 'achievements_xp', 'challenges_xp',
                 ]
        read_only_fields = ['user', 'completion_time', 'status']

    def get_is_record_broken(self, obj):
        if hasattr(obj, 'is_record_broken'):
            return bool(getattr(obj, 'is_record_broken'))
        if obj.status == 'completed' and obj.duration_seconds is not None and obj.track and obj.track.record_time_seconds is not None:
            return obj.duration_seconds == obj.track.record_time_seconds
        return False

    def get_base_xp(self, obj):
        return obj.track.base_xp_reward if obj.track else 0

    def get_record_bonus_xp(self, obj):
        # 50% бонус за рекорд
        if self.get_is_record_broken(obj):
            return int((obj.track.base_xp_reward if obj.track else 0) * 0.5)
        return 0

    def get_achievements_xp(self, obj):
        return sum([a.xp_reward for a in obj.earned_achievements.all()])

    def get_challenges_xp(self, obj):
        return sum([c.xp_reward for c in obj.completed_challenges.all()])

    def update(self, instance, validated_data):
        # Переопределяем update для обработки actual_route_data (если нужно)
        # Override update to handle actual_route_data (if needed)
        actual_route_data_geojson = validated_data.pop('actual_route_data', None)

        if actual_route_data_geojson:
             try:
                 # Преобразуем GeoJSON dict в объект LineString
                 # Convert GeoJSON dict to LineString object
                 instance.actual_route_data = LineString(actual_route_data_geojson['coordinates'])
             except Exception as e:
                  print(f"Error converting GeoJSON to LineString in update: {e}")
                  # Можно добавить более строгую обработку ошибок, если некорректные гео-данные недопустимы
                  # More strict error handling can be added if incorrect geo data is not allowed
                  pass # Позволяем обновить без гео-данных, если конвертация не удалась
              # Allow updating without geo data if conversion failed

        # Обновляем остальные поля
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

# Сериализатор для друзей
# Serializer for friends
class FriendSerializer(serializers.ModelSerializer):
    from_user = PublicUserSerializer(read_only=True)
    to_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all()) # Изменяем на PrimaryKeyRelatedField для записи
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Friend
        fields = ('id', 'from_user', 'to_user', 'status', 'created_at')
        read_only_fields = ('from_user', 'status', 'created_at') # 'to_user' теперь не read_only, чтобы можно было передавать ID

    # Переопределяем to_representation, чтобы to_user всегда сериализовался как полный PublicUserSerializer при чтении
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['to_user'] = PublicUserSerializer(instance.to_user, context=self.context).data
        return representation

class ActivityItemSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    # Включаем поля связанных моделей для отображения деталей события
    # Include related model fields to display event details
    # Например, для 'run_completed' будет доступна информация из связанного Run
    # For example, for 'run_completed', information from the related Run will be available
    run_distance_km = serializers.SerializerMethodField()
    achievement_name = serializers.ReadOnlyField(source='user_achievement.achievement.name')
    challenge_name = serializers.ReadOnlyField(source='user_challenge.challenge.name')
    friend_involved_user = serializers.ReadOnlyField(source='friend_relationship.to_user.username') # Для запросов в друзья
    # For friend requests
    level_reached = serializers.SerializerMethodField() # Метод для получения уровня при level_up
    # Method for getting the level on level_up
    race_track_name = serializers.ReadOnlyField(source='user_race_attempt.track.name') # Для гонок
    # For races
    race_duration_seconds = serializers.ReadOnlyField(source='user_race_attempt.duration_seconds')
    race_xp_earned = serializers.ReadOnlyField(source='user_race_attempt.xp_earned') # Для гонок
    # For races

    # Добавляем поле для данных о запланированной совместной пробежке
    # Add field for planned joint run data
    planned_joint_run_data = serializers.SerializerMethodField()

    # Добавляем поле для связанного пользователя (например, добавленный участник)
    # Add field for related user (e.g., added participant)
    related_user_username = serializers.ReadOnlyField(source='related_user.username')

    # Поле для отображения участников совместной пробежки
    # Field for displaying joint run participants
    joint_run_participants = serializers.SerializerMethodField()

    class Meta:
        model = ActivityItem
        fields = ['id', 'user', 'item_type', 'created_at',
                  'achievement_name', 'challenge_name', 'run_distance_km', 'friend_involved_user', 'level_reached',
                  'race_track_name', 'race_duration_seconds', 'race_xp_earned', # Поля для гонок
                  # Fields for races
                  'planned_joint_run_data', # Поле для совместных пробежек (можно оставить для полной информации, или убрать, если достаточно joint_run_participants)
                  # Field for joint runs (can be left for full information, or removed if joint_run_participants is sufficient)
                  'related_user_username', # Поле для связанного пользователя
                  # Field for related user
                  'joint_run_participants', # Новое поле для участников
                 ]
        # New field for participants

    def get_run_distance_km(self, obj):
        if obj.run and obj.run.distance_meters is not None:
            return round(obj.run.distance_meters / 1000, 2)
        return None

    def get_level_reached(self, obj):
        # Этот метод предполагает, что item_type == 'level_up_{level}'
        # This method assumes that item_type == 'level_up_{level}'
        if obj.item_type.startswith('level_up_'):
            try:
                return int(obj.item_type.split('_')[-1])
            except (ValueError, IndexError):
                return None
        return None

    # Метод для получения данных о запланированной совместной пробежке
    # Method for getting planned joint run data
    def get_planned_joint_run_data(self, obj):
        if obj.planned_joint_run:
            # Если запись связана с запланированной пробежкой напрямую, сериализуем ее
            # If the entry is directly related to a planned run, serialize it
            serializer = PlannedJointRunSerializer(obj.planned_joint_run, context=self.context)
            return serializer.data
        # Если запись связана через приглашение, и у приглашения есть planned_run, сериализуем ее
        # If the entry is related via an invitation, and the invitation has planned_run, serialize it
        # (Эта часть, возможно, уже не нужна, т.к. actual_runs напрямую ссылаются на PlannedJointRun)
        # (This part may no longer be needed, as actual_runs directly link to PlannedJointRun)
        # if obj.joint_run_invitation and hasattr(obj.joint_run_invitation, 'planned_run'):
        #     serializer = PlannedJointRunSerializer(obj.joint_run_invitation.planned_run, context=self.context)
        #     return serializer.data
        return None

    # Метод для получения имен участников совместной пробежки
    # Method for getting the names of joint run participants
    def get_joint_run_participants(self, obj):
        # Проверяем, связан ли элемент активности с PlannedJointRun
        # Check if the activity item is related to PlannedJointRun
        planned_run = None
        if obj.planned_joint_run:
            planned_run = obj.planned_joint_run
        # else: # Возможно, связан через Run, который связан с PlannedJointRun? (проверить)
        # else: # Possibly related via Run, which is related to PlannedJointRun? (check)
        #     if obj.run and obj.run.planned_joint_run:
        #         planned_run = obj.run.planned_joint_run

        if planned_run:
            # Возвращаем список имен участников
            # Return a list of participant usernames
            return [participant.username for participant in planned_run.participants.all()]
        return None

    def __str__(self):
        return f"{self.user.username} - {self.item_type} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# Сериализатор для приглашений на совместную пробежку
# Serializer for joint run invitations
class JointRunInvitationSerializer(serializers.ModelSerializer):
    # Изменяем sender и recipient, чтобы они использовали PublicUserSerializer для чтения
    sender = PublicUserSerializer(read_only=True)
    recipient = PublicUserSerializer(read_only=True) # При GET-запросах будет возвращать объект PublicUserSerializer

    # Добавляем поле recipient_id только для записи, чтобы фронтенд мог передавать ID получателя
    recipient_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='recipient', write_only=True)

    class Meta:
        model = JointRunInvitation
        fields = [
            'id', 'sender', 'recipient', 'recipient_id', 'status',
            'suggested_time', 'suggested_racetrack', 'meeting_location',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sender', 'recipient', 'status', 'created_at', 'updated_at',
            'suggested_racetrack' # Считаем, что suggested_racetrack будет установлен бэкендом после валидации
        ]
    
    # Валидация для suggested_time, чтобы оно было в будущем
    def validate_suggested_time(self, value):
        if value and value < timezone.now():
            raise serializers.ValidationError("Предложенное время не может быть в прошлом.")
        return value

    def create(self, validated_data):
        # 'recipient' будет уже в validated_data из-за source='recipient' в recipient_id
        return super().create(validated_data)

# Сериализатор для запланированных совместных пробежек
# Serializer for planned joint runs
class PlannedJointRunSerializer(serializers.ModelSerializer):
    participants = serializers.SlugRelatedField(many=True, read_only=True, slug_field='username') # Отображаем имена пользователей-участников
    # Display usernames of participants
    suggested_racetrack_name = serializers.ReadOnlyField(source='suggested_racetrack.name') # Отображаем имя трассы, если есть
    # Display track name if available
    actual_start_time = serializers.ReadOnlyField()

    class Meta:
        model = PlannedJointRun
        fields = ['id', 'invitation', 'participants', 'suggested_time', 'suggested_racetrack', 'suggested_racetrack_name', 'meeting_location', 'status', 'created_at', 'updated_at', 'actual_start_time']
        read_only_fields = ['id', 'invitation', 'participants', 'suggested_racetrack_name', 'created_at', 'updated_at', 'actual_start_time']

# Сериализатор для комментариев к элементам ленты активности
# Serializer for comments on activity feed items
class ActivityCommentSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username') # Отображаем имя пользователя, оставившего комментарий
    # Display name of the user who left the comment

    class Meta:
        model = ActivityComment
        fields = ['id', 'activity_item', 'user', 'text', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

# Сериализатор для блокировок
# Serializer for blocks
class BlockSerializer(serializers.ModelSerializer):
    blocker = serializers.ReadOnlyField(source='blocker.username')
    blocked_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='blocked', write_only=True)
    blocked = serializers.ReadOnlyField(source='blocked.username') # Это поле будет для чтения, чтобы показывать имя заблокированного пользователя

    class Meta:
        model = Block
        fields = ['id', 'blocker', 'blocked_id', 'blocked', 'created_at']
        read_only_fields = ['id', 'blocker', 'blocked', 'created_at']

# Сериализатор для отображения заблокированных пользователей (для пользователя, который блокировал)
# Serializer for displaying blocked users (for the user who blocked)
class BlockedUserSerializer(serializers.ModelSerializer):
    blocked_user = serializers.ReadOnlyField(source='blocked.username')
    blocked_user_id = serializers.ReadOnlyField(source='blocked.id')
    # Можно добавить больше полей заблокированного пользователя, если нужно (с учетом его приватности!)
    # More fields for the blocked user can be added if needed (considering their privacy!)

    class Meta:
        model = Block
        fields = ['id', 'blocked_user_id', 'blocked_user', 'created_at']
        read_only_fields = ['id', 'blocked_user_id', 'blocked_user', 'created_at']

class RaceLeaderboardEntrySerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    best_time_seconds = serializers.IntegerField()
    # Add other fields if needed, e.g., avatar, level etc.
    # Добавьте другие поля, если необходимо, например, аватар, уровень и т.д.

# Сериализатор для токенов устройств
# Serializer for device tokens
class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'token', 'device_type', 'created_at']
        read_only_fields = ['id', 'created_at']

# Add more serializers as needed...

class RaceFinishSerializer(serializers.Serializer):
    track_id = serializers.IntegerField()
    duration_seconds = serializers.IntegerField()
    # Принимаем GeoJSON geometry для маршрута
    route_definition = serializers.DictField() # Или serializers.JSONField() в зависимости от версии Django Rest Framework / Django

    def validate_track_id(self, value):
        from .models import RaceTrack
        try:
            RaceTrack.objects.get(id=value)
        except RaceTrack.DoesNotExist:
            raise serializers.ValidationError("Race track with this ID does not exist.")
        return value

    def validate_route_definition(self, value):
        # Basic validation for GeoJSON LineString structure
        if 'type' not in value or value['type'] != 'LineString':
            raise serializers.ValidationError("Invalid GeoJSON type. Expected 'LineString'.")
        if 'coordinates' not in value or not isinstance(value['coordinates'], list):
             raise serializers.ValidationError("Invalid GeoJSON structure. 'coordinates' must be a list.")
        # TODO: Add more comprehensive GeoJSON validation if needed
        # (e.g., check if coordinates are lists of numbers)
        return value

class RaceFinishView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = RaceFinishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        track_id = serializer.validated_data['track_id']
        duration_seconds = serializer.validated_data['duration_seconds']
        route_definition = serializer.validated_data['route_definition']

        try:
            race_track = RaceTrack.objects.get(id=track_id)
        except RaceTrack.DoesNotExist:
            return Response({'detail': 'Race track not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Преобразуем GeoJSON маршрут в объект LineString
        try:
            actual_route_data = LineString(route_definition['coordinates'], srid=4326) # Указываем SRID 4326
        except Exception as e:
            print(f"Error creating LineString from GeoJSON: {e}")
            return Response({'detail': 'Invalid route data.'}, status=status.HTTP_400_BAD_REQUEST)

        # Рассчитываем пройденную дистанцию на основе предоставленного маршрута
        # Note: This assumes the frontend is sending accurate route points.
        # A more robust solution might recalculate distance on the backend.
        # We'll use the distance from frontend for now as per serializer input.
        distance_covered_km = serializer.validated_data.get('distance_covered_km') # Получаем из сериализатора, если фронтенд отправляет

        # Если фронтенд не отправляет distance_covered_km, можно попробовать рассчитать его здесь
        # If frontend doesn't send distance_covered_km, you can try to calculate it here
        if distance_covered_km is None and actual_route_data:
             try:
                 distance_covered_km = actual_route_data.length / 1000.0 # length property is in meters for geographical LineStrings
             except Exception as e:
                 print(f"Error calculating distance from LineString: {e}")
                 distance_covered_km = 0.0 # Default to 0 if calculation fails


        # Рассчитываем опыт (пример: 1 XP за каждые 100 метров)
        # Calculate XP (example: 1 XP for every 100 meters)
        xp_earned = int((distance_covered_km * 1000) / 100) # Convert km to meters for calculation

        with transaction.atomic():
            # Создаем новую запись UserRaceAttempt
            user_race_attempt = UserRaceAttempt.objects.create(
                user=request.user,
                track=race_track,
                duration_seconds=duration_seconds,
                actual_route_data=actual_route_data,
                actual_distance_meters=distance_covered_km * 1000, # Сохраняем в метрах
                status='completed', # Устанавливаем статус завершено
                xp_earned=xp_earned,
                start_time=timezone.now() - timezone.timedelta(seconds=duration_seconds), # Приблизительное время старта
                completion_time=timezone.now()
            )

            # Обновляем опыт пользователя
            user_profile = request.user.profile
            user_profile.experience_points += xp_earned
            new_level = int(user_profile.experience_points / 1000) + 1
            if new_level > user_profile.level:
                user_profile.level = new_level
                ActivityItem.objects.create(user=request.user, item_type=f'level_up_{new_level}')

            user_profile.save()

            # Проверяем и обновляем рекорд трека
            if race_track.record_time_seconds is None or duration_seconds < race_track.record_time_seconds:
                race_track.record_time_seconds = duration_seconds
                race_track.save()
                # TODO: Возможно, создать ActivityItem для нового рекорда

            # TODO: Проверить выполнение челленджей, связанных с этой гонкой

            # Создаем ActivityItem для завершения гонки
            ActivityItem.objects.create(
                user=request.user,
                item_type='race_completed',
                user_race_attempt=user_race_attempt, # Связываем с записью попытки гонки
                is_published=True # Публикуем в ленте активности
            )


        # Возвращаем сериализованные данные о созданной попытке гонки
        response_serializer = UserRaceAttemptSerializer(user_race_attempt)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class SuggestedRouteSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')

    class Meta:
        model = SuggestedRoute
        fields = [
            'id', 'name', 'description', 'author', 'author_username',
            'route_points', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'author', 'status', 'created_at', 'author_username']
    