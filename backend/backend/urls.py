"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)
from core.views import UserRegistrationView, ProfileView, RunViewSet, UserRaceAttemptViewSet, RaceTrackViewSet, FriendViewSet, UserAchievementViewSet, UserChallengeViewSet, UserSearchView, UserProfilesViewSet, SuggestedRouteViewSet
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static

# Initialize router and register ViewSets
router = DefaultRouter()
router.register(r'runs', RunViewSet)
router.register(r'user-race-attempts', UserRaceAttemptViewSet)
router.register(r'race-tracks', RaceTrackViewSet)
router.register(r'friends', FriendViewSet)
router.register(r'user-achievements', UserAchievementViewSet)
router.register(r'user-challenges', UserChallengeViewSet)
router.register(r'users', UserSearchView, basename='user-search')
router.register(r'user-profiles', UserProfilesViewSet, basename='user-profile')
router.register(r'suggested-routes', SuggestedRouteViewSet, basename='suggestedroute')
# Register other ViewSets as needed

# Схема для Swagger UI и Redoc
schema_view = get_schema_view(
   openapi.Info(
      title="RunQuest API",
      default_version='v1',
      description="API для приложения RunQuest",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@runquest.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # API JWT Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # App URLs (including activity-feed from core.urls)
    path('api/', include('core.urls')),

    # Swagger/OpenAPI documentation
    path('swagger(<format>.json|.yaml)', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # ViewSet routes handled by the router
    path('api/friends/pending_requests/', FriendViewSet.as_view({'get': 'pending_requests'}), name='friend-pending-requests'),
    path('api/', include(router.urls)),

    # Additional routes (e.g., views not part of ViewSets)
    path('api/register/', UserRegistrationView.as_view(), name='register'),
    path('api/profile/', ProfileView.as_view(), name='profile'),

]

# Serving static and media files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
