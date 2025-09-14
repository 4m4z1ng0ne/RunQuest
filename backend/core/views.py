from django.shortcuts import render
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User, AnonymousUser
from rest_framework.decorators import action
from django.db.models import Q, F, Sum, Min, OuterRef, Subquery # Для сложных запросов
from rest_framework import serializers # Import serializers
from .serializers import (
    UserRegistrationSerializer,
    ProfileSerializer,
    RunSerializer,
    AchievementSerializer,
    ChallengeSerializer,
    UserAchievementSerializer,
    UserChallengeSerializer,
    RaceTrackSerializer,
    UserRaceAttemptSerializer,
    FriendSerializer,
    ActivityItemSerializer,
    RaceLeaderboardEntrySerializer,
    JointRunInvitationSerializer,
    PlannedJointRunSerializer,
    ActivityCommentSerializer,
    BlockSerializer,
    DeviceTokenSerializer,
    PublicUserSerializer,
    RaceFinishSerializer,
    SuggestedRouteSerializer,
)
from .models import (
    Profile,
    Run,
    Achievement,
    Challenge,
    UserAchievement,
    UserChallenge,
    RaceTrack,
    UserRaceAttempt,
    Friend,
    ActivityItem,
    JointRunInvitation,
    PlannedJointRun,
    ActivityComment,
    Block,
    DeviceToken,
    SuggestedRoute,
)
from django.db import transaction
from django.db.models import Count
from django.contrib.gis.geos import LineString
from django.utils import timezone
from .signals import check_secret_achievements
from .utils import calculate_xp_for_run, update_user_profile_xp_and_level, check_and_award_achievements, check_and_update_challenges, calculate_xp_for_race_attempt, check_for_race_record_broken # Import utility functions

# Пользовательские разрешения
# Custom permissions
class IsParticipantPlannedJointRun(permissions.BasePermission):
    """Проверяет, является ли пользователь участником запланированной совместной пробежки."""

    def has_object_permission(self, request, view, obj):
        # Проверяем, является ли пользователь участником PlannedJointRun
        if request.user.is_authenticated:
            return request.user in obj.participants.all()
        return False

# Импорт пагинации и фильтров
# Import pagination and filters
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

# Определение стандартного класса пагинации
# Define a standard pagination class
class StandardResultsPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 100

# Создайте ваши представления здесь.
# Create your views here.

class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = (permissions.AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({'detail': 'Пользователь успешно зарегистрирован'}, status=status.HTTP_201_CREATED, headers=headers)

class ProfileView(generics.RetrieveUpdateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        # Возвращаем профиль текущего аутентифицированного пользователя
        return self.request.user.profile

class RunViewSet(viewsets.ModelViewSet):
    queryset = Run.objects.all()
    serializer_class = RunSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Add pagination and filtering
    pagination_class = StandardResultsPagination
    filter_backends = [OrderingFilter, DjangoFilterBackend]
    ordering_fields = '__all__'
    filterset_fields = ['start_time', 'distance_meters', 'duration_seconds']

    def get_queryset(self):
        # Возвращаем только пробежки текущего пользователя по умолчанию
        user = self.request.user

        if not user.is_authenticated:
            return Run.objects.none()

        target_user_id = self.request.query_params.get('user_id')

        if not target_user_id or int(target_user_id) == user.id:
            return Run.objects.filter(user=user)

        try:
            target_user = User.objects.get(id=target_user_id)
            target_profile = Profile.objects.get(user=target_user)
        except (User.DoesNotExist, Profile.DoesNotExist):
            return Run.objects.none()

        is_friend = Friend.objects.filter(
            Q(from_user=user, to_user=target_user, status='accepted') |
            Q(from_user=target_user, to_user=user, status='accepted')
        ).exists()

        if target_profile.is_public or (target_profile.show_runs and is_friend):
            return Run.objects.filter(user=target_user)
        else:
            return Run.objects.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            planned_joint_run_id = serializer.validated_data.get('planned_joint_run')
            planned_run = None
            if planned_joint_run_id:
                try:
                    planned_run = PlannedJointRun.objects.get(id=planned_joint_run_id)
                    if not planned_run.actual_start_time:
                        print(f"PlannedJointRun {planned_joint_run_id} not started. Creating regular run.")
                        run = serializer.save(user=self.request.user)
                    else:
                        run = serializer.save(user=self.request.user, start_time=planned_run.actual_start_time)
                except PlannedJointRun.DoesNotExist:
                    print(f"PlannedJointRun with ID {planned_joint_run_id} not found. Creating a regular run.")
                    run = serializer.save(user=self.request.user)
            else:
                run = serializer.save(user=self.request.user)

            # Calculate XP for the run
            xp_earned_from_run = calculate_xp_for_run(run)
            run.xp_earned = xp_earned_from_run # Save XP to the model field

            # Update user profile XP and level
            update_user_profile_xp_and_level(run.user, xp_earned_from_run)

            # Check and award achievements
            newly_earned_achievements = check_and_award_achievements(run.user, run_data=serializer.validated_data)
            # Add achievements to the Run model field
            run.earned_achievements.set(newly_earned_achievements)

            # Check and update challenges
            newly_completed_challenges = check_and_update_challenges(run.user, run_data=serializer.validated_data)
            # Add challenges to the Run model field
            run.completed_challenges.set(newly_completed_challenges)

            # Ensure the run object is saved with the new fields
            run.save()
            run.refresh_from_db()

            # Manually construct the response data to ensure calculated fields are included
            response_data = RunSerializer(run, context={'request': request}).data
            # The fields are now part of the RunSerializer, no need to manually add them here
            # response_data['calculated_xp_earned'] = run.xp_earned # This field is directly in RunSerializer
            # response_data['completed_challenges_info'] = ChallengeSerializer(run.completed_challenges.all(), many=True).data # This field is directly in RunSerializer
            # response_data['earned_achievements_info'] = AchievementSerializer(run.earned_achievements.all(), many=True).data # This field is directly in RunSerializer

            headers = self.get_success_headers(response_data)
            return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Публикует результат тренировки в ленту активности."""
        try:
            run = self.get_queryset().get(pk=pk) # Use get_queryset to respect permissions
        except Run.DoesNotExist:
            return Response({'detail': 'Тренировка не найдена.'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the run belongs to the requesting user
        if run.user != request.user:
             return Response({'detail': 'У вас нет прав на публикацию этой тренировки.'}, status=status.HTTP_403_FORBIDDEN)

        # Create an ActivityItem for the published run
        # Check if an activity item for this run already exists to avoid duplicates
        if ActivityItem.objects.filter(run=run, item_type='run_published').exists():
             return Response({'detail': 'Результаты этой тренировки уже опубликованы.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                activity_item = ActivityItem.objects.create(
                    user=request.user,
                    item_type='run_published', # Define a new item type
                    run=run, # Link the activity item to the Run object
                    is_published=True # Mark as published
                )
                # You might want to add this item to followers' feeds, etc., here

            serializer = ActivityItemSerializer(activity_item)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"Error publishing run {run.id}: {e}")
            return Response({'detail': 'Не удалось опубликовать результаты тренировки.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ViewSets для геймификации

class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

class ChallengeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Challenge.objects.filter(is_active=True)
    serializer_class = ChallengeSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Позволяет пользователю присоединиться к челленджу."""
        try:
            challenge = self.get_object() # Получаем объект челленджа по pk
        except Challenge.DoesNotExist:
            return Response({'detail': 'Челлендж не найден.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user

        # Проверяем, аутентифицирован ли пользователь
        if not user.is_authenticated:
             return Response({'detail': 'Для присоединения к челленджу необходимо войти в систему.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Проверяем, участвует ли пользователь уже в этом челлендже
        if UserChallenge.objects.filter(user=user, challenge=challenge).exists():
            return Response({'detail': 'Вы уже участвуете в этом челлендже.'}, status=status.HTTP_400_BAD_REQUEST)

        # Создаем запись об участии пользователя в челлендже
        try:
            user_challenge = UserChallenge.objects.create(
                user=user,
                challenge=challenge,
                progress=0, # Начальный прогресс
                completed=False, # Пока не завершен
                completion_date=None # Дата завершения пока отсутствует
            )
            serializer = UserChallengeSerializer(user_challenge)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"Ошибка при создании UserChallenge: {e}")
            return Response({'detail': 'Не удалось присоединиться к челленджу.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserAchievementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserAchievement.objects.all()
    serializer_class = UserAchievementSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return UserAchievement.objects.none()

        target_user_id = self.request.query_params.get('user_id')

        if not target_user_id or int(target_user_id) == user.id:
            return self.queryset.filter(user=user)

        try:
            target_user = User.objects.get(id=target_user_id)
            target_profile = Profile.objects.get(user=target_user)
        except (User.DoesNotExist, Profile.DoesNotExist):
            return UserAchievement.objects.none()

        is_friend = Friend.objects.filter(
            Q(from_user=user, to_user=target_user, status='accepted') |
            Q(from_user=target_user, to_user=user, status='accepted')
        ).exists()

        if target_profile.is_public or (target_profile.show_achievements and is_friend):
            return self.queryset.filter(user=target_user)
        else:
            return UserAchievement.objects.none()

class UserChallengeViewSet(viewsets.ModelViewSet):
    queryset = UserChallenge.objects.all()
    serializer_class = UserChallengeSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        target_user_id = self.request.query_params.get('user_id')

        if target_user_id:
            try:
                target_user = User.objects.get(id=target_user_id)
                target_profile = Profile.objects.get(user=target_user)
                is_friend = False
                if user.is_authenticated:
                    is_friend = Friend.objects.filter(
                    Q(from_user=user, to_user=target_user, status='accepted') |
                    Q(from_user=target_user, to_user=user, status='accepted')
                ).exists()
                if not target_profile.show_challenges and not is_friend:
                    return UserChallenge.objects.none()
                else:
                    return UserChallenge.objects.filter(
                        user=target_user,
                        completed=True
                    ).order_by('-completion_date')[:2]
            except (User.DoesNotExist, Profile.DoesNotExist):
                return UserChallenge.objects.none()
        else:
            return UserChallenge.objects.filter(user=user).order_by('-completion_date')

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied("У вас нет разрешения на отмену участия в этом челлендже.")
        instance.delete()

# ViewSets для гонок на время
# ViewSets for timed races

class RaceTrackViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RaceTrack.objects.all()
    serializer_class = RaceTrackSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    @action(detail=False, methods=['get'])
    def start_points(self, request):
        start_points_data = []
        # Filter RaceTracks that have a route_definition and extract the first point
        race_tracks_with_routes = self.get_queryset().exclude(route_definition__isnull=True)
        for track in race_tracks_with_routes:
            if track.route_definition and track.route_definition.coords:
                # Assuming route_definition is a LineString and has at least one point
                start_coord = track.route_definition.coords[0]
                # The coords are typically (longitude, latitude) in Django GIS
                start_points_data.append({
                    'id': track.id,
                    'latitude': start_coord[1],
                    'longitude': start_coord[0],
                    'name': track.name # Include name for potential display
                })
        return Response(start_points_data, status=status.HTTP_200_OK)

class UserRaceAttemptViewSet(viewsets.ModelViewSet):
    queryset = UserRaceAttempt.objects.all()
    serializer_class = UserRaceAttemptSerializer
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = StandardResultsPagination
    filter_backends = [OrderingFilter, DjangoFilterBackend]
    ordering_fields = '__all__'
    filterset_fields = ['track', 'status']

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return self.queryset.filter(user=self.request.user)
        return UserRaceAttempt.objects.none()

    def perform_create(self, serializer):
        with transaction.atomic():
            race_attempt = serializer.save(user=self.request.user, status='completed') # Save with completed status

            # Check if a new record was broken
            is_record_broken = check_for_race_record_broken(race_attempt)
            race_attempt.is_record_broken = is_record_broken # Attach for serializer

            # Calculate XP for the race attempt
            xp_earned_from_race = calculate_xp_for_race_attempt(race_attempt, is_record_broken)
            race_attempt.xp_earned = xp_earned_from_race # Update the model field
            race_attempt.calculated_xp_earned = xp_earned_from_race # Attach for serializer
            race_attempt.save(update_fields=['xp_earned']) # Save the updated XP to the database

            # Update user profile XP and level
            update_user_profile_xp_and_level(race_attempt.user, xp_earned_from_race)

            # Check and award achievements
            newly_earned_achievements = check_and_award_achievements(race_attempt.user, race_attempt_data={'track_id': race_attempt.track.id})
            race_attempt.newly_earned_achievements = newly_earned_achievements # Attach for serializer

            # Check and update challenges
            newly_completed_challenges = check_and_update_challenges(race_attempt.user, race_attempt_data={'track_id': race_attempt.track.id})
            race_attempt.newly_completed_challenges = newly_completed_challenges # Attach for serializer

        leaderboard = UserRaceAttempt.objects.filter(
            track=race_attempt.track,
            status='completed',
        ).order_by('duration_seconds').select_related('user__profile')

        ranked_times = []
        current_rank = 0
        last_time = None

        for entry in leaderboard:
            if entry.duration_seconds is not None and (last_time is None or entry.duration_seconds > last_time):
                current_rank += 1
                last_time = entry.duration_seconds
                ranked_times.append((current_rank, entry.user.id, entry.duration_seconds))
            elif entry.duration_seconds == last_time:
                 ranked_times.append((current_rank, entry.user.id, entry.duration_seconds))


        user_rank = None
        for rank, user_id, time in ranked_times:
            if user_id == request.user.id:
                user_rank = rank
                break

        bonus_xp = 0
        if user_rank == 2:
            bonus_xp = 50
        elif user_rank == 3:
            bonus_xp = 30

        if bonus_xp > 0:
            user_profile, created = Profile.objects.get_or_create(user=request.user)
            user_profile.experience_points += bonus_xp
            user_profile.save()

            race_attempt.xp_earned += bonus_xp
            race_attempt.save(update_fields=['xp_earned'])

        is_published_race_completed = is_record_broken or (bonus_xp > 0)

        ActivityItem.objects.create(
            user=request.user,
            item_type='race_completed',
            user_race_attempt=race_attempt,
            is_published=is_published_race_completed
        )

        if is_record_broken:
             ActivityItem.objects.create(
                user=request.user,
                item_type='race_record_set',
                user_race_attempt=race_attempt,
                is_published=True
             )

        if bonus_xp > 0:
             ActivityItem.objects.create(
                user=request.user,
                item_type='race_ranked',
                user_race_attempt=race_attempt,
                is_published=True
             )

        race_attempt.refresh_from_db()
        serializer = self.get_serializer(race_attempt)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def cancel_race(self, request, pk=None):
        try:
            race_attempt = self.get_object()

            if race_attempt.status not in ['pending', 'in_progress']:
                return Response({'detail': f'Попытка гонки не может быть отменена из статуса {race_attempt.status}.'}, status=status.HTTP_400_BAD_REQUEST)

            race_attempt.status = 'cancelled'
            race_attempt.save()

            ActivityItem.objects.create(
                user=request.user,
                item_type='race_cancelled',
                user_race_attempt=race_attempt
            )

            serializer = self.get_serializer(race_attempt)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except UserRaceAttempt.DoesNotExist:
            return Response({'detail': 'Попытка гонки не найдена.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Произошла ошибка: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def publish_result(self, request, pk=None):
        try:
            race_attempt = self.get_object()

            if race_attempt.status != 'completed':
                return Response({'detail': 'Могут быть опубликованы только завершенные попытки гонки.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                activity_item = ActivityItem.objects.get(
                    user_race_attempt=race_attempt,
                    item_type='race_completed'
                )
            except ActivityItem.DoesNotExist:
                return Response({'detail': 'Элемент активности для этой попытки гонки не найден.'}, status=status.HTTP_404_NOT_FOUND)

            if not activity_item.is_published:
                activity_item.is_published = True
                activity_item.save()

            serializer = ActivityItemSerializer(activity_item)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except UserRaceAttempt.DoesNotExist:
            return Response({'detail': 'Попытка гонки не найдена.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Произошла ошибка: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def compare_route(self, request, pk=None):
        try:
            race_attempt = self.get_object()

            if race_attempt.status != 'completed':
                return Response({'detail': 'Сравнение маршрутов доступно только для завершенных гонок.'}, status=status.HTTP_400_BAD_REQUEST)

            if not race_attempt.actual_route_data or not race_attempt.track.route_definition:
                 return Response({'detail': 'Отсутствуют данные маршрута для сравнения.'}, status=status.HTTP_400_BAD_REQUEST)

            actual_route = race_attempt.actual_route_data
            track_route = race_attempt.track.route_definition

            try:
                comparison_results = UserRaceAttempt.objects.filter(pk=race_attempt.pk).annotate(
                    track_length=F('track__route_definition').length,
                    actual_length=F('actual_route_data').length,
                    intersection_geometry=actual_route.intersection(track_route)
                ).annotate(
                     intersection_length=F('intersection_geometry').length
                ).first()

                track_length = comparison_results.track_length
                intersection_length = comparison_results.intersection_length

                coverage_percentage = 0
                if track_length is not None and track_length > 0:
                    coverage_percentage = (intersection_length / track_length) * 100

                return Response({
                    'track_id': race_attempt.track.id,
                    'attempt_id': race_attempt.id,
                    'coverage_percentage': round(coverage_percentage, 2),
                    'track_length_meters': round(track_length, 2) if track_length is not None else None,
                    'intersection_length_meters': round(intersection_length, 2) if intersection_length is not None else None,
                }, status=status.HTTP_200_OK)

            except Exception as e:
                print(f"Error calculating route comparison: {e}")
                return Response({'detail': f'Ошибка при расчете сравнения маршрутов: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except UserRaceAttempt.DoesNotExist:
            return Response({'detail': 'Попытка гонки не найдена.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"An error occurred during route comparison: {e}")
            return Response({'detail': f'Произошла ошибка при сравнении маршрутов: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        track_id = request.query_params.get('track_id')
        if not track_id:
            return Response({'detail': 'Требуется параметр track_id.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            track = RaceTrack.objects.get(id=track_id)
        except RaceTrack.DoesNotExist:
            return Response({'detail': 'Гоночная трасса не найдена.'}, status=status.HTTP_404_NOT_FOUND)

        leaderboard_qs = UserRaceAttempt.objects.filter(
            track=track,
            status='completed',
            duration_seconds__isnull=False
        ).order_by('duration_seconds').select_related('user__profile')

        leaderboard_data = []
        current_rank = 0
        last_time = None

        for entry in leaderboard_qs:
            if entry.duration_seconds != last_time:
                current_rank += 1
                last_time = entry.duration_seconds

            username = (getattr(entry.user.profile, 'username', None) or entry.user.username or 'Без имени')

            leaderboard_data.append({
                'rank': current_rank,
                'username': username,
                'duration_seconds': entry.duration_seconds,
                'xp_earned': entry.xp_earned,
                'completion_time': entry.completion_time,
                'attempt_id': entry.id
            })

        page = self.paginate_queryset(leaderboard_data)
        if page is not None:
             return self.get_paginated_response(page)

        return Response(leaderboard_data)

# ViewSet для друзей
# ViewSet for friends
class FriendViewSet(viewsets.ModelViewSet):
    queryset = Friend.objects.all()
    serializer_class = FriendSerializer
    permission_classes = (permissions.IsAuthenticated,) # Возвращаем к IsAuthenticated
    pagination_class = StandardResultsPagination
    filter_backends = [OrderingFilter]
    ordering_fields = '__all__'

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous:
          return Friend.objects.none()
        # Возвращаем всех друзей, где текущий пользователь является from_user или to_user, со статусом 'accepted'
        return Friend.objects.filter(
            Q(from_user=user, status='accepted') | Q(to_user=user, status='accepted')
        )

    def perform_create(self, serializer):
        print(f"DEBUG: perform_create: request.data={self.request.data}")
        print(f"DEBUG: perform_create: serializer.is_valid()={serializer.is_valid()}")
        if not serializer.is_valid():
            print(f"DEBUG: perform_create: serializer.errors={serializer.errors}")

        from_user = self.request.user
        to_user_id_obj = serializer.validated_data.get('to_user')
        print(f"DEBUG: perform_create: from_user={from_user.username}, to_user_id_obj={to_user_id_obj}")
        to_user = User.objects.get(id=to_user_id_obj.id)

        if to_user == from_user:
            raise serializers.ValidationError('Нельзя отправить запрос дружбы самому себе.')

        # Проверка блокировки перед созданием запроса
        if Block.objects.filter(blocker=from_user, blocked=to_user).exists() or \
           Block.objects.filter(blocker=to_user, blocked=from_user).exists():
            raise serializers.ValidationError('Невозможно отправить запрос этому пользователю из-за настроек блокировки.')

        # Проверяем, существует ли уже такой запрос (pending, accepted, etc.)
        if Friend.objects.filter(
             Q(from_user=from_user, to_user=to_user) | Q(from_user=to_user, to_user=from_user)
        ).exclude(status='rejected').exists():
            raise serializers.ValidationError('Запрос дружбы уже существует или уже принят.')

        friend_request = serializer.save(from_user=from_user, to_user=to_user) # Передаем to_user
        ActivityItem.objects.create(user=friend_request.from_user, item_type='friend_request_sent', friend_relationship=friend_request)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        print(f"DEBUG: accept: pk={pk}")
        print(f"DEBUG: accept: request.user.id={request.user.id}")
        print(f"DEBUG: accept: Attempting to get Friend object with pk={pk}, to_user={request.user.id}, status='pending'")
        try:
            friend_request = Friend.objects.get(pk=pk, to_user=request.user, status='pending')
            print(f"DEBUG: accept: friend_request.id={friend_request.id}, from_user={friend_request.from_user.username}, to_user={friend_request.to_user.username}, status={friend_request.status}")
            # if friend_request.to_user != self.request.user:
            #     return Response({'detail': 'Запрещено принимать этот запрос.'}, status=status.HTTP_403_FORBIDDEN)

            # Проверка блокировки перед принятием запроса
            if Block.objects.filter(blocker=friend_request.to_user, blocked=friend_request.from_user).exists() or \
               Block.objects.filter(blocker=friend_request.from_user, blocked=friend_request.to_user).exists():
                 return Response({'detail': 'Невозможно принять этот запрос из-за настроек блокировки.'}, status=status.HTTP_400_BAD_REQUEST)

            friend_request.status = 'accepted'
            friend_request.save()

            ActivityItem.objects.create(user=friend_request.from_user, item_type='friend_request_accepted', friend_relationship=friend_request)
            ActivityItem.objects.create(user=friend_request.to_user, item_type='friend_request_accepted', friend_relationship=friend_request)

            # Выдача секретного достижения за первого друга (и тому, и другому)
            check_secret_achievements(friend_request.from_user, friend_added=True)
            check_secret_achievements(friend_request.to_user, friend_added=True)

            serializer = self.get_serializer(friend_request)
            return Response(serializer.data)
        except Friend.DoesNotExist:
            print(f"DEBUG: accept: Friend.DoesNotExist for pk={pk}")
            return Response({'detail': 'Запрос на добавление в друзья не найден.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        print(f"DEBUG: reject: pk={pk}")
        print(f"DEBUG: reject: request.user.id={request.user.id}")
        print(f"DEBUG: reject: Attempting to get Friend object with pk={pk}, to_user={request.user.id}, status='pending'")
        try:
            friend_request = Friend.objects.get(pk=pk, to_user=request.user, status='pending')
            print(f"DEBUG: reject: friend_request.id={friend_request.id}, from_user={friend_request.from_user.username}, to_user={friend_request.to_user.username}, status={friend_request.status}")
            # if friend_request.to_user != self.request.user:
            #     return Response({'detail': 'Запрещено отклонять этот запрос.'}, status=status.HTTP_403_FORBIDDEN)

            friend_request.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Friend.DoesNotExist:
            print(f"DEBUG: reject: Friend.DoesNotExist for pk={pk}")
            return Response({'detail': 'Запрос на добавление в друзья не найден.'}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not (request.user == instance.from_user or request.user == instance.to_user):
            return Response({"detail": "У вас нет прав для выполнения этого действия."},
                            status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def cancel_sent(self, request, pk=None):
        print(f"DEBUG: cancel_sent: pk={pk}")
        print(f"DEBUG: cancel_sent: request.user.id={request.user.id}")
        print(f"DEBUG: cancel_sent: Attempting to get Friend object with pk={pk}, from_user={request.user.id}, status='pending'")
        try:
            friend_request = Friend.objects.get(pk=pk, from_user=request.user, status='pending')
            print(f"DEBUG: cancel_sent: friend_request.id={friend_request.id}, from_user={friend_request.from_user.username}, to_user={friend_request.to_user.username}, status={friend_request.status}")
            # if friend_request.from_user != self.request.user:
            #     return Response({'detail': 'Вы не являетесь отправителем этого запроса.'}, status=status.HTTP_403_FORBIDDEN)

            # if friend_request.status != 'pending':
            #     return Response({'detail': f'Этот запрос нельзя отменить, т.к. он уже {friend_request.status}.'}, status=status.HTTP_400_BAD_REQUEST)

            friend_request.delete()

            ActivityItem.objects.create(
                user=request.user,
                item_type='friend_request_cancelled',
                related_user=friend_request.to_user
            )

            return Response(status=status.HTTP_204_NO_CONTENT)
        except Friend.DoesNotExist:
            print(f"DEBUG: cancel_sent: Friend.DoesNotExist for pk={pk}")
            return Response({'detail': 'Запрос на добавление в друзья не найден.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"DEBUG: cancel_sent: Exception type: {type(e)}")
            print(f"Error cancelling friend request: {e}")
            return Response({'detail': f'Произошла ошибка: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def my_friends(self, request):
        friends = self.queryset.filter(Q(from_user=request.user, status='accepted') | Q(to_user=request.user, status='accepted'))
        serializer = self.get_serializer(friends, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_requests(self, request):
        pending_requests = self.queryset.filter(to_user=request.user, status='pending')
        serializer = self.get_serializer(pending_requests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def sent_requests(self, request):
        sent_requests = self.queryset.filter(from_user=request.user, status='pending')
        serializer = self.get_serializer(sent_requests, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def invite_for_run(self, request, pk=None):
        try:
            friend_relationship = self.get_object()

            if friend_relationship.status != 'accepted' or (friend_relationship.from_user != request.user and friend_relationship.to_user != request.user):
                 return Response({'detail': 'Недействительные или непринятые отношения дружбы.'}, status=status.HTTP_400_BAD_REQUEST)

            recipient_user = friend_relationship.to_user if friend_relationship.from_user == request.user else friend_relationship.from_user

            if recipient_user == request.user:
                 return Response({'detail': 'Нельзя отправить приглашение на совместную пробежку самому себе.'}, status=status.HTTP_400_BAD_REQUEST)

            suggested_time_str = request.data.get('suggested_time')
            suggested_racetrack_id = request.data.get('suggested_racetrack')
            meeting_location = request.data.get('meeting_location')

            if not suggested_time_str and not suggested_racetrack_id and not meeting_location:
                 return Response({'detail': 'Необходимо указать хотя бы suggested_time, suggested_racetrack или meeting_location.'}, status=status.HTTP_400_BAD_REQUEST)

            suggested_time = None
            if suggested_time_str:
                try:
                    suggested_time = timezone.datetime.fromisoformat(suggested_time_str)
                except ValueError:
                    return Response({'detail': 'Неверный формат даты и времени для suggested_time. Используйте ISO 8601.'}, status=status.HTTP_400_BAD_REQUEST)

            suggested_racetrack = None
            if suggested_racetrack_id:
                try:
                    suggested_racetrack = RaceTrack.objects.get(id=suggested_racetrack_id)
                except RaceTrack.DoesNotExist:
                    return Response({'detail': 'Гоночная трасса с этим ID не существует.'}, status=status.HTTP_400_BAD_REQUEST)

            invitation = JointRunInvitation.objects.create(
                sender=request.user,
                recipient=recipient_user,
                suggested_time=suggested_time,
                suggested_racetrack=suggested_racetrack,
                meeting_location=meeting_location,
                status='pending'
            )

            ActivityItem.objects.create(
                user=request.user,
                item_type='joint_run_invitation_sent',
                joint_run_invitation=invitation
            )

            serializer = JointRunInvitationSerializer(invitation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Friend.DoesNotExist:
            return Response({'detail': 'Отношения дружбы не найдены.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error sending joint run invitation: {e}")
            return Response({'detail': f'Произошла ошибка при отправке приглашения на совместную пробежку: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def friendship_status(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({'detail': 'Аутентификация не предоставлена.'}, status=status.HTTP_401_UNAUTHORIZED)

        target_user_id = request.query_params.get('user_id')
        if not target_user_id:
            return Response({'detail': 'Требуется user_id.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response({'detail': 'Пользователь не найден.'}, status=status.HTTP_404_NOT_FOUND)

        if user == target_user:
             return Response({'status': 'self'}, status=status.HTTP_200_OK)

        # Проверяем, заблокировал ли текущий пользователь целевого, или наоборот
        if Block.objects.filter(blocker=user, blocked=target_user).exists() or \
           Block.objects.filter(blocker=target_user, blocked=user).exists():
            return Response({'status': 'blocked'}, status=status.HTTP_200_OK)

        # Проверяем статус дружбы
        friendship = Friend.objects.filter(
            Q(from_user=user, to_user=target_user) | Q(from_user=target_user, to_user=user)
        ).first()

        if friendship:
            if friendship.status == 'accepted':
                return Response({'status': 'accepted', 'id': friendship.id}, status=status.HTTP_200_OK)
            elif friendship.status == 'pending':
                if friendship.from_user == user:
                    return Response({'status': 'pending_sent', 'id': friendship.id}, status=status.HTTP_200_OK)
                else:
                    return Response({'status': 'pending_received', 'id': friendship.id}, status=status.HTTP_200_OK)
        else:
            return Response({'status': 'not_friends'}, status=status.HTTP_200_OK)

# Вью для ленты активности
# View for activity feed
class ActivityFeedView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = StandardResultsPagination
    filter_backends = [OrderingFilter]
    ordering_fields = '__all__'

    def get(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({'detail': 'Аутентификация не предоставлена.'}, status=status.HTTP_401_UNAUTHORIZED)

        friend_ids = Friend.objects.filter(
            Q(from_user=user, status='accepted') | Q(to_user=user, status='accepted')
        ).values_list('from_user_id', 'to_user_id')

        friend_user_ids = set()
        for from_id, to_id in friend_ids:
            if from_id != user.id:
                friend_user_ids.add(from_id)
            if to_id != user.id:
                friend_user_ids.add(to_id)

        # Получаем ID пользователей, которых заблокировал текущий пользователь
        blocked_by_me_ids = Block.objects.filter(blocker=user).values_list('blocked_id', flat=True)

        # Получаем ID пользователей, которые заблокировали текущего пользователя
        blocked_me_ids = Block.objects.filter(blocked=user).values_list('blocker_id', flat=True)

        # Объединяем списки ID заблокированных пользователей
        blocked_user_ids = list(blocked_by_me_ids) + list(blocked_me_ids)

        activity_items = ActivityItem.objects.filter(
            Q(user=user) |
            Q(user__id__in=friend_user_ids, is_published=True)
        ).exclude(user__id__in=blocked_user_ids).order_by('-created_at') # Исключаем записи от заблокированных пользователей и сортируем

        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(activity_items, request, view=self)

        if paginated_queryset is not None:
            serializer = ActivityItemSerializer(paginated_queryset, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        else:
            serializer = ActivityItemSerializer(activity_items, many=True, context={'request': request})
            return Response(serializer.data)

# Добавление нового ViewSet для таблицы лидеров гонки
# Add the new ViewSet for Race Leaderboard
class RaceLeaderboardView(generics.ListAPIView):
    serializer_class = RaceLeaderboardEntrySerializer
    pagination_class = StandardResultsPagination
    filter_backends = [OrderingFilter]
    ordering_fields = '__all__'

    def get_queryset(self):
        track_id = self.kwargs['racetrack_pk']
        best_attempts = UserRaceAttempt.objects.filter(
            race_track_id=track_id,
            status='completed'
        ).values('user').annotate(best_time=Min('duration_seconds'))

        leaderboard_entries = User.objects.filter(
            id__in=Subquery(best_attempts.values('user'))
        ).annotate(
            best_time_seconds=Subquery(
                best_attempts.filter(user=OuterRef('id'))
                .values('best_time')[:1]
            )
        ).order_by('best_time_seconds')

        return leaderboard_entries.values('id', 'username', 'best_time_seconds')

# Добавление нового ViewSet для приглашений на совместную пробежку
# Add the new ViewSet for Joint Run Invitations
class JointRunInvitationViewSet(viewsets.ModelViewSet):
    queryset = JointRunInvitation.objects.all()
    serializer_class = JointRunInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status'] # Разрешаем фильтрацию по статусу через параметры запроса

    def get_queryset(self):
        user = self.request.user
        queryset = JointRunInvitation.objects.all()

        # Фильтруем приглашения, где пользователь является отправителем ИЛИ получателем
        # Filter invitations where the user is either the sender OR the recipient
        queryset = queryset.filter(Q(sender=user) | Q(recipient=user))

        # Дополнительная фильтрация по статусу, если он предоставлен
        # Additional filtering by status if provided
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # НОВОЕ: Добавляем фильтрацию по типу запроса (входящие/исходящие)
        # NEW: Add filtering by request type (received/sent)
        type_param = self.request.query_params.get('type')
        if type_param == 'received':
            queryset = queryset.filter(recipient=user)
        elif type_param == 'sent':
            queryset = queryset.filter(sender=user)

        return queryset

    def perform_create(self, serializer):
        sender = self.request.user
        recipient = serializer.validated_data.get('recipient')

        # Проверка блокировки перед созданием приглашения
        if Block.objects.filter(blocker=sender, blocked=recipient).exists() or \
           Block.objects.filter(blocker=recipient, blocked=sender).exists():
            return Response({'detail': 'Невозможно отправить приглашение этому пользователю из-за настроек блокировки.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer.save(sender=sender)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        invitation = self.get_object()
        if invitation.recipient != request.user:
            return Response({'detail': 'Вы не являетесь получателем этого приглашения.'}, status=status.HTTP_403_FORBIDDEN)

        if invitation.status != 'pending':
            return Response({'detail': f'Это приглашение уже находится в статусе {invitation.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        invitation.status = 'accepted'
        invitation.updated_at = timezone.now()
        invitation.save()

        ActivityItem.objects.create(
            user=invitation.sender,
            item_type='joint_run_invitation_accepted',
            joint_run_invitation=invitation
        )
        ActivityItem.objects.create(
            user=invitation.recipient,
            item_type='joint_run_invitation_accepted',
            joint_run_invitation=invitation
        )

        planned_run = PlannedJointRun.objects.create(
            invitation=invitation,
            suggested_time=invitation.suggested_time,
            suggested_racetrack=invitation.suggested_racetrack,
            meeting_location=invitation.meeting_location,
            status='planned'
        )
        planned_run.participants.add(invitation.sender, invitation.recipient)

        serializer = self.get_serializer(invitation)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        invitation = self.get_object()
        if invitation.recipient != request.user:
            return Response({'detail': 'Вы не являетесь получателем этого приглашения.'}, status=status.HTTP_403_FORBIDDEN)

        if invitation.status != 'pending':
            return Response({'detail': f'Это приглашение уже находится в статусе {invitation.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        invitation.status = 'rejected'
        invitation.updated_at = timezone.now()
        invitation.save()

        ActivityItem.objects.create(
            user=invitation.sender,
            item_type='joint_run_invitation_rejected',
            joint_run_invitation=invitation
        )
        ActivityItem.objects.create(
            user=invitation.recipient,
            item_type='joint_run_invitation_rejected',
            joint_run_invitation=invitation
        )

        serializer = self.get_serializer(invitation)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        invitation = self.get_object()
        if invitation.sender != request.user:
            return Response({'detail': 'Вы не являетесь отправителем этого приглашения.'}, status=status.HTTP_403_FORBIDDEN)

        if invitation.status not in ['pending', 'accepted']:
             return Response({'detail': f'Это приглашение не может быть отменено, т.к. оно имеет статус {invitation.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        invitation.status = 'cancelled'
        invitation.updated_at = timezone.now()
        invitation.save()

        ActivityItem.objects.create(
            user=invitation.sender,
            item_type='joint_run_invitation_cancelled',
            joint_run_invitation=invitation
        )
        ActivityItem.objects.create(
            user=invitation.recipient,
            item_type='joint_run_invitation_cancelled',
            joint_run_invitation=invitation
        )

        serializer = self.get_serializer(invitation)
        return Response(serializer.data)

# Добавление нового ViewSet для запланированных совместных пробежек
# Add the new ViewSet for Planned Joint Runs
class PlannedJointRunViewSet(viewsets.ModelViewSet):
    queryset = PlannedJointRun.objects.all()
    serializer_class = PlannedJointRunSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Возвращаем только предстоящие пробежки, в которых участвует текущий пользователь,
        # и которые находятся в статусе 'planned' или 'accepted'.
        return PlannedJointRun.objects.filter(
            participants=user,
            suggested_time__gte=timezone.now(),
            status__in=['planned', 'accepted']
        ).order_by('suggested_time')

    def perform_update(self, serializer):
        planned_run = self.get_object()
        user = self.request.user

        if user not in planned_run.participants.all():
             return Response({'detail': 'Вы не являетесь участником этой запланированной пробежки.'}, status=status.HTTP_403_FORBIDDEN)

        old_suggested_time = planned_run.suggested_time
        old_meeting_location = planned_run.meeting_location

        serializer.save()

        time_changed = old_suggested_time != planned_run.suggested_time
        location_changed = old_meeting_location != planned_run.meeting_location

        if time_changed or location_changed:
            if time_changed and location_changed:
                item_type = 'joint_run_details_changed'
            elif time_changed:
                item_type = 'joint_run_time_changed'
            else:
                item_type = 'joint_run_location_changed'

            for participant in planned_run.participants.all():
                 ActivityItem.objects.create(
                    user=participant,
                    item_type=item_type,
                    planned_joint_run=planned_run,
                 )

    def perform_destroy(self, instance):
        if self.request.user not in instance.participants.all():
             return Response({'detail': 'Вы не являетесь участником этой запланированной пробежки.'}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        try:
            planned_run = self.get_object()
            user = request.user

            if user not in planned_run.participants.all():
                 return Response({'detail': 'Вы не являетесь участником этой запланированной пробежки.'}, status=status.HTTP_403_FORBIDDEN)

            participant_user_id = request.data.get('user_id')
            if not participant_user_id:
                return Response({'detail': 'Необходимо указать user_id пользователя для добавления.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                participant_user = User.objects.get(id=participant_user_id)
            except User.DoesNotExist:
                 return Response({'detail': 'Пользователь с указанным user_id не найден.'}, status=status.HTTP_404_NOT_FOUND)

            is_friend = Friend.objects.filter(
                Q(from_user=user, to_user=participant_user, status='accepted') |
                Q(from_user=participant_user, to_user=user, status='accepted')
            ).exists()

            if not is_friend:
                 return Response({'detail': 'Вы можете добавить только своих друзей.'}, status=status.HTTP_400_BAD_REQUEST)

            if participant_user in planned_run.participants.all():
                 return Response({'detail': 'Этот пользователь уже является участником пробежки.'}, status=status.HTTP_400_BAD_REQUEST)

            planned_run.participants.add(participant_user)

            for participant in planned_run.participants.all():
                 ActivityItem.objects.create(
                    user=participant,
                    item_type='joint_run_participant_added',
                    planned_joint_run=planned_run,
                    related_user=participant_user,
                 )

            serializer = self.get_serializer(planned_run)
            return Response(serializer.data)

        except PlannedJointRun.DoesNotExist:
            return Response({'detail': 'Запланированная совместная пробежка не найдена.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error adding participant to joint run: {e}")
            return Response({'detail': f'Произошла ошибка: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsParticipantPlannedJointRun])
    def start(self, request, pk=None):
        planned_run = self.get_object()

        if planned_run.actual_start_time:
            return Response({'detail': 'Совместная пробежка уже началась.'}, status=status.HTTP_400_BAD_REQUEST)

        planned_run.actual_start_time = timezone.now()
        planned_run.status = 'in_progress'
        planned_run.save()

        for participant in planned_run.participants.all():
            ActivityItem.objects.create(
                user=participant,
                item_type='joint_run_started',
                planned_joint_run=planned_run,
            )

        serializer = self.get_serializer(planned_run)
        return Response(serializer.data)

# Добавление нового ViewSet для комментариев к активности
# Add the new ViewSet for Activity Comments
class ActivityCommentViewSet(viewsets.ModelViewSet):
    queryset = ActivityComment.objects.all()
    serializer_class = ActivityCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ActivityComment.objects.all()

    def perform_create(self, serializer):
        activity_item_pk = self.kwargs.get('activity_item_pk')
        try:
            activity_item = ActivityItem.objects.get(pk=activity_item_pk)
        except ActivityItem.DoesNotExist:
            return Response({'detail': 'Запись ленты активности не найдена.'}, status=status.HTTP_404_NOT_FOUND)

        if not activity_item.allow_comments:
            return Response({'detail': 'Комментарии к этой записи отключены.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer.save(user=self.request.user, activity_item=activity_item)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.user != self.request.user:
            return Response({'detail': 'Вы не можете редактировать этот комментарий.'}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()

    def perform_destroy(self, instance):
        activity_item_owner = instance.activity_item.user
        if instance.user == self.request.user or activity_item_owner == self.request.user:
            instance.delete()
        else:
            return Response({'detail': 'Вы не можете удалить этот комментарий.'}, status=status.HTTP_403_FORBIDDEN)

# Новый ViewSet для просмотра профилей других пользователей
# New ViewSet for viewing other users' profiles
class UserProfilesViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Profile.objects.none()

        friend_ids = Friend.objects.filter(
            Q(from_user=user, status='accepted') | Q(to_user=user, status='accepted')
        ).values_list('from_user_id', 'to_user_id')

        friend_user_ids = set()
        for from_id, to_id in friend_ids:
            if from_id != user.id:
                friend_user_ids.add(from_id)
            if to_id != user.id:
                friend_user_ids.add(to_id)

        # Исключаем пользователей, заблокированных текущим пользователем или заблокировавших текущего пользователя
        blocked_users_ids = Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list('blocked__id', 'blocker__id')
        all_blocked_ids = set()
        for blocker_id, blocked_id in blocked_users_ids:
            all_blocked_ids.add(blocker_id)
            all_blocked_ids.add(blocked_id)
        
        return self.queryset.filter(
            Q(user=user) |
            Q(user__id__in=list(friend_user_ids)) |
            Q(is_public=True)
        ).exclude(user__id__in=list(all_blocked_ids)).distinct()

    def retrieve(self, request, pk=None, *args, **kwargs):
        try:
            instance = Profile.objects.get(user__id=pk) # Fetch profile directly by user ID (pk)
        except Profile.DoesNotExist:
            return Response({'detail': 'Профиль пользователя не найден.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user

        # The serializer will handle field-level permissions based on the relationship
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='block')
    def block_user(self, request, pk=None):
        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'Пользователь не найден.'}, status=status.HTTP_404_NOT_FOUND)

        if target_user == request.user:
            return Response({'detail': 'Вы не можете заблокировать самого себя.'}, status=status.HTTP_400_BAD_REQUEST)

        if Block.objects.filter(blocker=request.user, blocked=target_user).exists():
            return Response({'detail': 'Этот пользователь уже заблокирован вами.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                Block.objects.create(blocker=request.user, blocked=target_user)
                # Удаляем все дружеские связи при блокировке
                Friend.objects.filter(
                    Q(from_user=request.user, to_user=target_user) |
                    Q(from_user=target_user, to_user=request.user)
                ).delete()
                # Отменяем ожидающие приглашения на совместные пробежки
                JointRunInvitation.objects.filter(
                    Q(sender=request.user, recipient=target_user, status='pending') |
                    Q(sender=target_user, recipient=request.user, status='pending')
                ).update(status='cancelled')

            return Response({'detail': 'Пользователь успешно заблокирован.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': f'Ошибка при блокировке пользователя: {e}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='unblock')
    def unblock_user(self, request, pk=None):
        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'Пользователь не найден.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            block_instance = Block.objects.get(blocker=request.user, blocked=target_user)
            block_instance.delete()
            return Response({'detail': 'Пользователь успешно разблокирован.'}, status=status.HTTP_200_OK)
        except Block.DoesNotExist:
            return Response({'detail': 'Этот пользователь не был заблокирован вами.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'detail': f'Ошибка при разблокировке пользователя: {e}'}, status=status.HTTP_400_BAD_REQUEST)

# Новый ViewSet для поиска пользователей
# New ViewSet for searching users
class UserSearchView(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = PublicUserSerializer
    permission_classes = (permissions.IsAuthenticated,) # Возвращаем к IsAuthenticated

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['username']
    ordering_fields = ['username', 'date_joined']

    def get_queryset(self):
        print(f"UserSearchView: request.user: {self.request.user}")
        print(f"UserSearchView: request.user.is_authenticated: {self.request.user.is_authenticated}")
        print(f"UserSearchView: request.auth: {self.request.auth}")
        queryset = User.objects.all()
        # Исключаем текущего пользователя из результатов поиска
        if self.request.user.is_authenticated:
            queryset = queryset.exclude(id=self.request.user.id)
        return queryset

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            # Используем Q-объекты для выполнения регистронезависимого поиска по имени пользователя
            # и исключаем текущего пользователя из результатов
            users = self.get_queryset().filter(username__icontains=query)
        else:
            users = User.objects.none() # Если запрос пустой, возвращаем пустой набор данных
        
        # Применяем пагинацию к результатам поиска
        page = self.paginate_queryset(users)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(users, many=True)
        return Response(serializer.data)

# Новый ViewSet для управления блокировками
# New ViewSet for managing blocks
class BlockViewSet(viewsets.ModelViewSet):
    queryset = Block.objects.all()
    serializer_class = BlockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(blocker=self.request.user)

    def perform_create(self, serializer):
        # blocked_id теперь будет обрабатываться сериализатором и передаваться как blocked_user
        blocked_user = serializer.validated_data['blocked']

        if blocked_user == self.request.user:
            raise serializers.ValidationError('Вы не можете заблокировать самого себя.')

        # Проверяем, заблокирован ли пользователь уже
        if Block.objects.filter(blocker=self.request.user, blocked=blocked_user).exists():
            raise serializers.ValidationError('Этот пользователь уже заблокирован вами.')

        try:
            block_instance = serializer.save(blocker=self.request.user, blocked=blocked_user)

            # При блокировке пользователя удаляем все дружеские связи между ними
            Friend.objects.filter(
                Q(from_user=self.request.user, to_user=blocked_user) |
                Q(from_user=blocked_user, to_user=self.request.user)
            ).delete()
            # Также отменяем любые ожидающие приглашения на совместные пробежки
            JointRunInvitation.objects.filter(
                 Q(sender=self.request.user, recipient=blocked_user, status='pending') |
                 Q(sender=blocked_user, recipient=self.request.user, status='pending')
            ).update(status='cancelled')

        except Exception as e:
            print(f"Error creating block: {e}")
            raise serializers.ValidationError(f'Не удалось создать блокировку: {e}')

    def perform_destroy(self, instance):
        if instance.blocker != self.request.user:
            return Response({'detail': 'Вы не можете удалить эту блокировку.'}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    @action(detail=False, methods=['get'])
    def is_blocked(self, request):
        target_user_id = request.query_params.get('user_id')
        if not target_user_id:
            return Response({'detail': 'Необходимо указать user_id пользователя для проверки.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response({'detail': 'Пользователь не найден.'}, status=status.HTTP_404_NOT_FOUND)

        is_blocked_by_viewer = Block.objects.filter(blocker=request.user, blocked=target_user).exists()
        viewer_is_blocked = Block.objects.filter(blocker=target_user, blocked=request.user).exists()

        return Response({
            'is_blocked_by_viewer': is_blocked_by_viewer,
            'viewer_is_blocked': viewer_is_blocked
        })

# Новый ViewSet для управления токенами устройств
# New ViewSet for managing device tokens
class DeviceTokenViewSet(viewsets.ModelViewSet):
    queryset = DeviceToken.objects.all()
    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        token = serializer.validated_data.get('token')
        device_type = serializer.validated_data.get('device_type')

        try:
            device_token = DeviceToken.objects.get(user=self.request.user, token=token)
            serializer.instance = device_token
            return Response(serializer.data, status=status.HTTP_200_OK)
        except DeviceToken.DoesNotExist:
            serializer.save(user=self.request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        instance.delete()

# Добавление нового View для завершения гонки
# Add the new View for race completion
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
                start_time=timezone.now() - timezone.timedelta(seconds=duration_seconds), # Приблизительное время старта
                completion_time=timezone.now()
            )

            # --- Новая логика как в UserRaceAttemptViewSet ---
            # Проверяем, побит ли рекорд
            is_record_broken = check_for_race_record_broken(user_race_attempt)
            user_race_attempt.is_record_broken = is_record_broken # Для сериализации

            # Считаем XP по правилам гонки
            xp_earned = calculate_xp_for_race_attempt(user_race_attempt, is_record_broken)
            user_race_attempt.xp_earned = xp_earned
            user_race_attempt.save(update_fields=['xp_earned'])

            # Обновляем профиль пользователя
            update_user_profile_xp_and_level(request.user, xp_earned)

            # Достижения
            newly_earned_achievements = check_and_award_achievements(request.user, race_attempt_data={'track_id': track_id})
            user_race_attempt.earned_achievements.set(newly_earned_achievements)

            # Челленджи
            newly_completed_challenges = check_and_update_challenges(request.user, race_attempt_data={'track_id': track_id})
            user_race_attempt.completed_challenges.set(newly_completed_challenges)

            user_race_attempt.save()

            # ActivityItem для завершения гонки
            ActivityItem.objects.create(
                user=request.user,
                item_type='race_completed',
                user_race_attempt=user_race_attempt, # Связываем с записью попытки гонки
                is_published=True # Публикуем в ленте активности
            )


        # Возвращаем сериализованные данные о созданной попытке гонки
        response_serializer = UserRaceAttemptSerializer(user_race_attempt)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class SuggestedRouteViewSet(viewsets.ModelViewSet):
    queryset = SuggestedRoute.objects.all()
    serializer_class = SuggestedRouteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SuggestedRoute.objects.all()
        return SuggestedRoute.objects.filter(author=user)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
