from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models import Sum
from django.utils import timezone
from .models import Profile, Run, UserRaceAttempt, Achievement, Challenge, UserAchievement, UserChallenge, ActivityItem, RaceTrack
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import LineString # Импортируем LineString
from django.contrib.gis.measure import D # Импортируем D для работы с расстояниями
from django.contrib.gis.db.models.functions import Intersection, Length # Импортируем гео-функции

User = get_user_model()

# Процент совпадения маршрута, необходимый для получения XP за гонку
MIN_ROUTE_MATCH_PERCENTAGE = 80 # Example: 80% match required for full XP

# Сигнал для автоматического создания профиля пользователя при регистрации нового пользователя
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Используем get_or_create, чтобы избежать ошибки, если профиль уже существует
        Profile.objects.get_or_create(user=instance)
        # Создаем элемент активности для регистрации пользователя
        # Create an activity item for user registration
        ActivityItem.objects.create(
            user=instance,
            item_type='user_registered',
            is_published=True # Публикуем по умолчанию
        )

# Сигнал для сохранения профиля пользователя при сохранении объекта пользователя
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Проверяем, существует ли профиль, прежде чем пытаться его сохранить (на случай, если create_user_profile еще не отработал)
    # Check if the profile exists before trying to save it (in case create_user_profile hasn't run yet)
    if hasattr(instance, 'profile'):
        instance.profile.save()

def create_achievement_activity_item(user, achievement, user_achievement):
    """Helper to create an activity item for earning an achievement."""
    try:
        activity_text = f'{user.username} получил достижение "{achievement.name}"!'
        ActivityItem.objects.create(
            user=user,
            item_type='achievement_earned',
            user_achievement=user_achievement # Link to UserAchievement
        )
        print(f"Activity item created for achievement: {activity_text}")
    except Profile.DoesNotExist:
        print(f"Profile does not exist for user {user.username}. Cannot create activity item for achievement.")
    except Exception as e:
        print(f"Error creating activity item for achievement: {e}")

def create_challenge_activity_item(user, challenge, user_challenge):
    """Helper to create an activity item for completing a challenge."""
    try:
        activity_text = f'{user.username} завершил челлендж "{challenge.name}"!'
        ActivityItem.objects.create(
            user=user,
            item_type='challenge_completed',
            user_challenge=user_challenge # Link to UserChallenge
        )
        print(f"Activity item created for challenge: {activity_text}")
    except Profile.DoesNotExist:
        print(f"Profile does not exist for user {user.username}. Cannot create activity item for challenge.")
    except Exception as e:
        print(f"Error creating activity item for challenge: {e}")

def check_secret_achievements(user, run=None, friend_added=False):
    """
    Проверяет и выдает секретные достижения по особым условиям:
    - Первый друг
    - Пробежка ровно 1000 метров
    - Пробежка ночью (00:00-01:00)
    """
    from .models import Achievement, UserAchievement
    from django.utils import timezone
    now = timezone.now()
    # 1. Первый друг
    if friend_added:
        secret_ach = Achievement.objects.filter(is_secret=True, name__icontains='друг').first()
        if secret_ach:
            user_achievement, created = UserAchievement.objects.get_or_create(user=user, achievement=secret_ach)
            if not user_achievement.completed:
                user_achievement.completed = True
                user_achievement.completion_date = now
                user_achievement.save()
                user.profile.experience_points += secret_ach.xp_reward
                user.profile.save()
                create_achievement_activity_item(user, secret_ach, user_achievement)
    # 2. Пробежка ровно 1000 метров
    if run and run.distance_meters is not None and abs(run.distance_meters - 1000) < 1:
        secret_ach = Achievement.objects.filter(is_secret=True, name__icontains='1000').first()
        if secret_ach:
            user_achievement, created = UserAchievement.objects.get_or_create(user=user, achievement=secret_ach)
            if not user_achievement.completed:
                user_achievement.completed = True
                user_achievement.completion_date = now
                user_achievement.save()
                user.profile.experience_points += secret_ach.xp_reward
                user.profile.save()
                create_achievement_activity_item(user, secret_ach, user_achievement)
    # 3. Пробежка ночью (00:00-01:00)
    if run and run.start_time.hour == 0:
        secret_ach = Achievement.objects.filter(is_secret=True, name__icontains='ноч').first()
        if secret_ach:
            user_achievement, created = UserAchievement.objects.get_or_create(user=user, achievement=secret_ach)
            if not user_achievement.completed:
                user_achievement.completed = True
                user_achievement.completion_date = now
                user_achievement.save()
                user.profile.experience_points += secret_ach.xp_reward
                user.profile.save()
                create_achievement_activity_item(user, secret_ach, user_achievement)

def check_run_achievements(user, run):
    """
    Checks and awards achievements based on a completed run.
    """
    # Include specific_route achievements in checks, but main logic is in race attempts
    achievements_to_check = Achievement.objects.filter(achievement_type__in=['run_count', 'distance', 'duration', 'specific_route'])

    # Calculate total run count and total distance for the user
    total_run_count = user.runs.count()
    total_distance_meters = user.runs.aggregate(Sum('distance_meters'))['distance_meters__sum'] or 0

    for achievement in achievements_to_check:
        user_achievement, created = UserAchievement.objects.get_or_create(user=user, achievement=achievement)

        if not user_achievement.completed and achievement.target_value is not None:
            is_completed = False

            if achievement.achievement_type == 'run_count':
                if total_run_count >= achievement.target_value:
                    is_completed = True

            elif achievement.achievement_type == 'distance':
                 if total_distance_meters >= achievement.target_value:
                     is_completed = True

            elif achievement.achievement_type == 'duration' and run.duration_seconds is not None:
                 # Check duration for the current run
                 if run.duration_seconds >= achievement.target_value:
                     is_completed = True

            elif achievement.achievement_type == 'specific_route':
                 # Check specific_route achievement ONLY if the run is linked to a racetrack (e.g., via a related field on Run model, if added)
                 # Or if we assume specific_route achievements are only for race attempts.
                 # Given the separate check_race_attempt_achievements function, let's primarily handle specific_route there.
                 # Keep this placeholder in case runs can also be linked to routes/tracks directly in the future.
                 pass # Logic for specific_route for runs is complex and depends on route matching.


            if is_completed:
                user_achievement.completed = True
                user_achievement.completion_date = timezone.now() # Use current time as completion time
                user_achievement.save()
                # Award XP when achievement is completed via signal
                user_profile, created = Profile.objects.get_or_create(user=user)
                user_profile.experience_points += achievement.xp_reward
                user_profile.save()
                # Create activity item for earning achievement
                create_achievement_activity_item(user, achievement, user_achievement)

    # После основной проверки достижений вызываем проверку секретных
    check_secret_achievements(user, run=run)

def check_race_attempt_achievements_and_challenges(user, race_attempt):
    """
    Checks and awards achievements/challenges based on a completed race attempt.
    """
    # Assuming race attempt is considered 'completed' when duration_seconds is set.
    if race_attempt.duration_seconds is None: # Only process completed attempts
        return

    # Define a threshold for route matching percentage (e.g., 90%)
    # TODO: Make this threshold configurable (e.g., in settings or Achievement model)
    MIN_ROUTE_MATCH_PERCENTAGE = 90.0

    # --- Achievement Logic ---
    achievements_to_check = Achievement.objects.filter(achievement_type__in=['race_count', 'specific_route'])
    # TODO: Add achievement type for beating race record.

    # Calculate total race count for the user
    total_race_count = user.race_attempts.filter(duration_seconds__isnull=False).count()

    for achievement in achievements_to_check:
        user_achievement, created = UserAchievement.objects.get_or_create(user=user, achievement=achievement)

        if not user_achievement.completed and achievement.target_value is not None:
            is_completed = False

            if achievement.achievement_type == 'race_count':
                if total_race_count >= achievement.target_value:
                    is_completed = True

            elif achievement.achievement_type == 'specific_route':
                 # Check specific_route achievement if it's linked to the completed track
                 if achievement.related_racetrack and race_attempt.track == achievement.related_racetrack:
                     # Check if both the track route and actual route data are available
                     if race_attempt.actual_route_data and achievement.related_racetrack.route_definition:
                         try:
                             # Calculate the intersection of the actual route and the defined track route
                             # and the lengths of both
                             actual_route = race_attempt.actual_route_data
                             track_route = achievement.related_racetrack.route_definition

                             # Ensure both geometries are valid before attempting intersection
                             if actual_route.valid and track_route.valid:
                                 intersection_geometry = actual_route.intersection(track_route)

                                 # Calculate the length of the intersection and the track route
                                 intersection_length_meters = intersection_geometry.length # Length in meters because geography=True
                                 track_length_meters = track_route.length # Length in meters

                                 # Calculate coverage percentage
                                 coverage_percentage = 0
                                 if track_length_meters is not None and track_length_meters > 0:
                                     coverage_percentage = (intersection_length_meters / track_length_meters) * 100

                                 print(f"[SIGNAL] Specific Route Achievement Check: Track '{achievement.related_racetrack.name}', Attempt {race_attempt.id}")
                                 print(f"[SIGNAL] Coverage Percentage: {coverage_percentage:.2f}%")
                                 print(f"[SIGNAL] Required Coverage: {MIN_ROUTE_MATCH_PERCENTAGE}%")

                                 # Check if the coverage percentage meets the minimum requirement
                                 if coverage_percentage >= MIN_ROUTE_MATCH_PERCENTAGE:
                                     is_completed = True
                                     print(f"[SIGNAL] Specific Route Achievement '{achievement.name}' completed!")
                                 else:
                                     print(f"[SIGNAL] Specific Route Achievement '{achievement.name}' not completed: coverage below threshold.")

                             else:
                                 print(f"[SIGNAL] Specific Route Achievement Check: Invalid geometry data for attempt {race_attempt.id} or track {achievement.related_racetrack.id}.")

                         except Exception as e:
                             # Handle potential errors during geospatial calculations
                             print(f"[SIGNAL] Error during specific_route achievement check for attempt {race_attempt.id}: {e}")
                             is_completed = False # Assume not completed if there's an error

                     else:
                         print(f"[SIGNAL] Specific Route Achievement Check: Missing route data for attempt {race_attempt.id} or track {achievement.related_racetrack.id}.")

            # TODO: Implement logic for race attempt specific achievements (e.g., beating race record time). This would likely need new achievement types.

            if is_completed:
                user_achievement.completed = True
                user_achievement.completion_date = timezone.now()
                user_achievement.save()
                # Award XP when achievement is completed via signal
                user_profile, created = Profile.objects.get_or_create(user=user)
                user_profile.experience_points += achievement.xp_reward
                user_profile.save()
                # Create activity item for earning achievement
                create_achievement_activity_item(user, achievement, user_achievement)

    # --- Challenge Logic ---
    # Update progress and check completion for race-attempt-based challenges
    # Find active, incomplete challenges related to race attempts or specific tracks
    active_challenges = UserChallenge.objects.filter(
        user=user,
        challenge__is_active=True,
        completed=False,
        challenge__challenge_type__in=['complete_racetrack'] # Filter for relevant challenge types
    )

    print(f"[SIGNAL] Found {active_challenges.count()} active race-based challenges for user {user.username} in the initial filter.") # Debug print

    # Let's try to find the specific challenge for Track 1 directly
    track1_challenge = UserChallenge.objects.filter(
        user=user,
        challenge__is_active=True,
        challenge__challenge_type='complete_racetrack',
        challenge__related_racetrack__id=1 # Assuming Track 1 has ID 1
    ).first()

    if track1_challenge:
        print(f"[SIGNAL] Found specific 'complete_racetrack' challenge for Track 1 (ID: {track1_challenge.id}). Completed status: {track1_challenge.completed}") # Debug print
        # Now process this specific challenge
        if not track1_challenge.completed and race_attempt.track == track1_challenge.challenge.related_racetrack:
             print(f"[SIGNAL] Conditions met for completing challenge '{track1_challenge.challenge.name}'. Attempt track: {race_attempt.track.id}, Challenge track: {track1_challenge.challenge.related_racetrack.id}") # Debug print

             track1_challenge.completed = True
             track1_challenge.completion_date = timezone.now()
             track1_challenge.progress = track1_challenge.challenge.target_value or 1 # Mark progress as completed
             print(f'[SIGNAL] Race challenge "{track1_challenge.challenge.name}" completed!') # Debug print error

             try:
                 track1_challenge.save()
                 print(f"[SIGNAL] Saved user_challenge '{track1_challenge.challenge.name}' as completed.") # Debug print error

                 # Award XP when challenge is completed via signal
                 user_profile, created = Profile.objects.get_or_create(user=user)
                 user_profile.experience_points += track1_challenge.challenge.xp_reward # Начисляем опыт за челлендж
                 user_profile.save() # Сохраняем профиль после начисления опыта за челлендж
                 print(f"[SIGNAL] Awarded {track1_challenge.challenge.xp_reward} XP to user {user.username}. New XP: {user_profile.experience_points}") # Debug print error

                 # Create activity item for completing challenge
                 create_challenge_activity_item(user, track1_challenge.challenge, track1_challenge)
             except Exception as e:
                  print(f"[SIGNAL] Error saving track1_challenge or awarding XP: {e}") # Debug print error
        else:
            print(f"[SIGNAL] Specific 'complete_racetrack' challenge for Track 1 found but not completed. Completed: {track1_challenge.completed}, Attempt track matches challenge track: {race_attempt.track == track1_challenge.challenge.related_racetrack}") # Debug print why not completed
    else:
         print(f"[SIGNAL] Specific 'complete_racetrack' challenge for Track 1 not found for user {user.username}") # Debug print if challenge not found


    # The loop below for active_challenges might still be useful for other race-based types if added later
    # But for 'complete_racetrack', the specific check above is more direct.
    # Keep the loop for potential future expansion
    for user_challenge in active_challenges:
        # This loop will now likely show 0 challenges if the Track 1 challenge was just completed
        # but it's good to keep for other potential future race-based challenge types
        print(f"[SIGNAL] Processing challenge in loop '{user_challenge.challenge.name}' (type: {user_challenge.challenge.challenge_type})") # Debug print
        # Original logic from here... (can keep or remove depending on future needs)


    # Note: Activity feed item for race completion is created in UserRaceAttemptViewSet complete action.


# TODO: Refine achievement logic (e.g., specific routes, tiered achievements).
# TODO: Implement logic for race attempt specific achievements (e.g., beating record time).
# TODO: Ensure Activity Items are created consistently for all achievement and challenge completions.