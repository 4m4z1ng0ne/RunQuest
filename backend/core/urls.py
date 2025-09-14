from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Создание роутера и регистрация наших ViewSets
router = DefaultRouter()
# router.register(r'users', views.UserViewSet) # Если есть UserViewSet, иначе пропустить
router.register(r'runs', views.RunViewSet)
router.register(r'achievements', views.AchievementViewSet)
router.register(r'challenges', views.ChallengeViewSet)
router.register(r'user-achievements', views.UserAchievementViewSet)
router.register(r'user-challenges', views.UserChallengeViewSet)
router.register(r'racetracks', views.RaceTrackViewSet)
router.register(r'user-race-attempts', views.UserRaceAttemptViewSet)
router.register(r'friends', views.FriendViewSet)
router.register(r'joint-run-invitations', views.JointRunInvitationViewSet, basename='joint-run-invitation')
router.register(r'planned-joint-runs', views.PlannedJointRunViewSet, basename='planned-joint-run')
router.register(r'user-profiles', views.UserProfilesViewSet, basename='user-profile')
router.register(r'user-search', views.UserSearchView, basename='user-search')
router.register(r'blocks', views.BlockViewSet, basename='block')

# Создаем вложенный маршрутизатор для комментариев к записям ленты активности
activity_item_router = DefaultRouter()
activity_item_router.register(r'comments', views.ActivityCommentViewSet, basename='activity-item-comments')

# URL-паттерны для API
urlpatterns = [
    path('register/', views.UserRegistrationView.as_view(), name='user-register'),
    path('profile/', views.ProfileView.as_view(), name='user-profile'),
    path('activity-feed/', views.ActivityFeedView.as_view(), name='activity-feed'),
    # Вложенные URL для комментариев к записям ленты активности
    path('activity-feed/<int:activity_item_pk>/', include(activity_item_router.urls)), # Вложенные URL для комментариев
    # URL-ы, сгенерированные основным маршрутизатором
    path('', include(router.urls)),
    # URL для завершения гонки
    path('race/finish/', views.RaceFinishView.as_view(), name='race-finish'), # Добавляем новый паттерн
]