from django.urls import path
from inventory.feature_views import (
    InventoryFeatureViewSet,
    CompanyInventoryFeatureViewSet,
)

# Feature management URLs
urlpatterns = [
    path('features/',
         InventoryFeatureViewSet.as_view({'get': 'list'}),
         name='inventory-features-list'),
    path('features/<uuid:pk>/',
         InventoryFeatureViewSet.as_view({'get': 'retrieve'}),
         name='inventory-features-detail'),
    path('company-features/',
         CompanyInventoryFeatureViewSet.as_view({
             'get': 'list',
             'put': 'update_features',
         }),
         name='inventory-company-features'),
    path('company-features/<uuid:pk>/',
         CompanyInventoryFeatureViewSet.as_view({'get': 'retrieve'}),
         name='inventory-company-features-detail'),
]
