from django.contrib import admin

from .models import Blend, DeviceStatus, Injection, StockEvent


class InjectionInline(admin.TabularInline):
    model = Injection
    extra = 0


@admin.register(Blend)
class BlendAdmin(admin.ModelAdmin):
    list_display = ("started_at", "mood_name", "completed", "finished_at")
    inlines = [InjectionInline]


admin.site.register(DeviceStatus)
admin.site.register(StockEvent)
