from django.db.models import F
from django.utils import timezone
from .models import Profile, UserAchievement, Achievement, UserChallenge, Challenge, Run, UserRaceAttempt, RaceTrack
from django.db.models import Sum
from django.contrib.gis.geos import LineString
from django.contrib.gis.measure import D
from django.db.models.functions import Length

def calculate_xp_for_run(run: Run):
    xp_earned = 0
    if run.distance_meters:
        xp_earned += int(run.distance_meters / 10) # 100 XP per KM
    if run.duration_seconds:
        xp_earned += int(run.duration_seconds / 60) # 1 XP per minute
    return xp_earned

def calculate_xp_for_race_attempt(attempt: UserRaceAttempt, is_record_broken: bool):
    xp_earned = 0
    track = attempt.track
    xp_earned += track.base_xp_reward
    if track.record_time_seconds and attempt.duration_seconds and attempt.duration_seconds > track.record_time_seconds:
        penalty = int((attempt.duration_seconds - track.record_time_seconds) * track.xp_penalty_per_second)
        xp_earned = max(0, xp_earned - penalty) # Ensure XP doesn't go below zero
    if is_record_broken:
        xp_earned += int(track.base_xp_reward * 0.5) # 50% bonus for breaking record
    if attempt.status == 'completed':
        xp_earned = max(xp_earned, track.base_xp_reward)
    return xp_earned

def update_user_profile_xp_and_level(user, xp_amount):
    """Updates user's XP and checks for level up."""
    profile, created = Profile.objects.get_or_create(user=user)
    profile.experience_points += xp_amount

    # Simple leveling system (e.g., level up every 1000 XP)
    # This can be made more complex with a lookup table if needed
    current_level = profile.level
    # Check for level up
    while profile.experience_points >= current_level * 1000: # Example: level 1 needs 1000, level 2 needs 2000 total etc.
        profile.level += 1
        current_level = profile.level # Update current_level for the next iteration
        # Optionally, award bonus XP/achievements for leveling up
    profile.save()

def check_and_award_achievements(user, run_data: dict = None, race_attempt_data: dict = None):
    """
    Checks if any achievements are unlocked based on user activity.
    Returns a list of newly earned achievements.
    """
    newly_earned_achievements = []
    
    # Get user's current total distance and run count (for 'distance' and 'run_count' achievements)
    total_distance_meters = Run.objects.filter(user=user).aggregate(Sum('distance_meters'))['distance_meters__sum'] or 0
    total_run_count = Run.objects.filter(user=user).count()
    
    # Get user's current total race count
    total_race_count = UserRaceAttempt.objects.filter(user=user, status='completed').count()

    # Get achievements not yet earned by the user
    earned_achievements_ids = UserAchievement.objects.filter(user=user).values_list('achievement__id', flat=True)
    available_achievements = Achievement.objects.exclude(id__in=earned_achievements_ids)

    for achievement in available_achievements:
        unlocked = False
        if achievement.achievement_type == 'distance' and achievement.target_value is not None:
            if total_distance_meters >= achievement.target_value:
                unlocked = True
        elif achievement.achievement_type == 'run_count' and achievement.target_value is not None:
            if total_run_count >= achievement.target_value:
                unlocked = True
        elif achievement.achievement_type == 'race_count' and achievement.target_value is not None:
            if total_race_count >= achievement.target_value:
                unlocked = True
        elif achievement.achievement_type == 'specific_route' and achievement.related_racetrack:
            # Check if the user has completed this specific race track
            if race_attempt_data and race_attempt_data.get('track_id') == achievement.related_racetrack.id:
                unlocked = True
        # Add more achievement types as needed (e.g., 'duration')

        if unlocked:
            UserAchievement.objects.create(
                user=user,
                achievement=achievement,
                completed=True,
                completion_date=timezone.now(),
                received_at=timezone.now() # Ensure received_at is set
            )
            newly_earned_achievements.append(achievement)
            update_user_profile_xp_and_level(user, achievement.xp_reward) # Award XP for achievement

    return newly_earned_achievements

def check_and_update_challenges(user, run_data: dict = None, race_attempt_data: dict = None):
    newly_completed_challenges = []
    active_challenges = UserChallenge.objects.filter(user=user, completed=False)
    for user_challenge in active_challenges:
        challenge = user_challenge.challenge
        updated_progress = user_challenge.progress
        if challenge.challenge_type == 'distance_goal' and challenge.target_value is not None and run_data:
            updated_progress += run_data.get('distance_meters', 0)
        elif challenge.challenge_type == 'duration_goal' and challenge.target_value is not None and run_data:
            updated_progress += run_data.get('duration_seconds', 0)
        elif challenge.challenge_type == 'run_count_goal' and challenge.target_value is not None and run_data:
            updated_progress += 1 
        elif challenge.challenge_type == 'complete_racetrack' and challenge.related_racetrack and race_attempt_data:
            if race_attempt_data.get('track_id') == challenge.related_racetrack.id:
                updated_progress = challenge.target_value 
        user_challenge.progress = updated_progress
        if user_challenge.progress >= (challenge.target_value 
                                       if challenge.target_value is not None else 0):
            user_challenge.completed = True
            user_challenge.completion_date = timezone.now()
            newly_completed_challenges.append(challenge)
            update_user_profile_xp_and_level(user, challenge.xp_reward) 
        user_challenge.save()
    return newly_completed_challenges

def check_for_race_record_broken(race_attempt: UserRaceAttempt):
    """Checks if the current race attempt broke the track record."""
    track = race_attempt.track
    
    # If no record exists, or current attempt is faster, update the record
    if track.record_time_seconds is None or (race_attempt.duration_seconds and race_attempt.duration_seconds < track.record_time_seconds):
        track.record_time_seconds = race_attempt.duration_seconds
        track.save(update_fields=['record_time_seconds'])
        return True
    
    return False 
