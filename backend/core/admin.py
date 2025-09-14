from django.contrib import admin, messages
from .models import Profile, Achievement, Challenge, RaceTrack, Run, UserRaceAttempt, UserAchievement, UserChallenge, Friend, PlannedJointRun, ActivityItem, JointRunInvitation, ActivityComment, Block, DeviceToken, SuggestedRoute
from django.contrib.gis import admin as gis_admin
from leaflet.admin import LeafletGeoAdmin
from django.contrib.gis.db.models.functions import Length # Импортируем Length для использования в действии
from django import forms

admin.site.register(Profile)
admin.site.register(Achievement)
admin.site.register(Challenge)
admin.site.register(Run)
admin.site.register(UserRaceAttempt)
admin.site.register(UserAchievement)
admin.site.register(UserChallenge)
admin.site.register(Friend)
admin.site.register(PlannedJointRun)
admin.site.register(ActivityItem)
admin.site.register(JointRunInvitation)
admin.site.register(ActivityComment)
admin.site.register(Block)
admin.site.register(DeviceToken)

class SuggestedRouteAdminForm(forms.ModelForm):
    class Meta:
        model = SuggestedRoute
        fields = '__all__'

    class Media:
        js = (
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'js/suggestedroute_map.js',  # твой кастомный JS
        )
        css = {
            'all': ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',)
        }

@admin.register(SuggestedRoute)
class SuggestedRouteAdmin(admin.ModelAdmin):
    form = SuggestedRouteAdminForm
    readonly_fields = ('created_at',)
    list_display = ('name', 'author', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'author__username', 'description')
    actions = ['approve_routes', 'reject_routes']

    def approve_routes(self, request, queryset):
        queryset.update(status='approved')
    approve_routes.short_description = "Одобрить выбранные маршруты"

    def reject_routes(self, request, queryset):
        queryset.update(status='rejected')
    reject_routes.short_description = "Отклонить выбранные маршруты"

class RaceTrackAdmin(LeafletGeoAdmin):
    # Здесь можно добавить дополнительные настройки админки, если нужно
    # readonly_fields = ('length_meters',)
    # Если вы хотите, чтобы поле length_meters заполнялось JS, оно не должно быть readonly
    # Вместо readonly_fields = ('length_meters',)
    # Возможно, вам придется временно убрать его из readonly_fields
    # или использовать hidden input и JS для его заполнения.
    # Давайте пока оставим readonly_fields, но JS будет пытаться его заполнить.
    # Если не получится из-за readonly, придется убрать эту настройку.

    change_form_template = 'admin/core/racetrack/change_form.html' # Указываем кастомный шаблон

    actions = ['calculate_selected_track_lengths'] # Регистрируем наше новое действие

    def calculate_selected_track_lengths(self, request, queryset):
        "Calculates and updates the length_meters for selected RaceTracks."
        updated_count = 0
        # Аннотируем queryset с calculated_length, используя функцию Length базы данных
        queryset_with_length = queryset.annotate(calculated_length=Length('route_definition'))

        for track_with_length in queryset_with_length:
            if track_with_length.route_definition:
                try:
                    # Теперь access calculated_length from the annotated object
                    calculated_length_obj = track_with_length.calculated_length
                    # Извлекаем значение в метрах (.m)
                    calculated_length = calculated_length_obj.m

                    # Получаем оригинальный объект track из базы данных для сохранения
                    # Это нужно, потому что annotated queryset может не быть готовым к сохранению напрямую
                    original_track = RaceTrack.objects.get(pk=track_with_length.pk)
                    original_track.length_meters = calculated_length
                    original_track.save() # Сохраняем объект с обновленной длиной
                    updated_count += 1
                except Exception as e:
                    self.message_user(request, f"Ошибка при расчете длины для трассы {track_with_length.name}: {e}", messages.ERROR)
            else:
                self.message_user(request, f"Трасса {track_with_length.name} не имеет определения маршрута.", messages.WARNING)

        self.message_user(request, f"Успешно обновлена длина для {updated_count} трасс.", messages.SUCCESS)

    calculate_selected_track_lengths.short_description = "Рассчитать длину выбранных трасс" # Название действия в админке

    pass

# Убираем стандартную регистрацию RaceTrack и регистрируем с кастомным RaceTrackAdmin
# admin.site.unregister(RaceTrack) # Сначала отменяем стандартную регистрацию
admin.site.register(RaceTrack, RaceTrackAdmin) # Регистрируем с кастомным классом
