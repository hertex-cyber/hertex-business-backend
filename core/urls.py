from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "healthy"})

urlpatterns = [
    path('', health_check),
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/contacts/', include('contacts.urls')),
    path('api/', include('invoices.urls')),
    path('api/', include('menus.urls')),
    path('api/crm/', include('crm.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/hr/', include('hr.urls')),
    path('api/sales/', include('sales_task_manager.urls')),
    path('api/', include('media.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/inventory/', include('inventory.feature_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
