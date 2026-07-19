from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from inventory.models import InventoryFeature, CompanyInventoryFeature
from inventory.feature_serializers import (
    InventoryFeatureSerializer,
    InventoryFeatureListSerializer,
    CompanyInventoryFeatureSerializer,
    CompanyFeatureToggleSerializer,
)
from inventory.feature_helpers import get_company_inventory_features


def _get_tenant_id(request):
    """Helper to get tenant_id (organization_id) from request user."""
    if not request.user.is_authenticated:
        return None
    return request.user.organization_id


class InventoryFeatureViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/inventory/features/ — Return all global inventory features.

    Superadmin/Admin can see all features, including inactive ones via ?show_inactive=true
    """

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'is_active': ['exact'],
    }
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['display_order', 'code', 'name']
    ordering = ['display_order', 'name']

    def get_serializer_class(self):
        if self.action == 'list':
            return InventoryFeatureListSerializer
        return InventoryFeatureSerializer

    def get_queryset(self):
        qs = InventoryFeature.objects.all()
        show_inactive = self.request.query_params.get('show_inactive', 'false') == 'true'
        if not show_inactive:
            qs = qs.filter(is_active=True)
        return qs


class CompanyInventoryFeatureViewSet(viewsets.ViewSet):
    """
    View and manage company-specific inventory feature configurations.

    GET    /api/inventory/company-features/               → Current company's features
    PUT    /api/inventory/company-features/               → Enable/disable features for current company
    GET    /api/inventory/company-features/{company_id}/  → View another company's config (admin only)
    """

    def get_company(self, request, company_id=None):
        """Get the target company — either current user's org or specified (admin only)."""
        if company_id:
            # Admin viewing another company's configuration
            if request.user.role not in ['Superadmin', 'Admin']:
                return None
            from menus.models import Organization
            try:
                return Organization.objects.get(id=company_id)
            except Organization.DoesNotExist:
                return None
        return request.user.organization

    def list(self, request):
        """
        GET /api/inventory/company-features/
        Return enabled features for the current company.
        """
        company = self.get_company(request)
        if not company:
            return Response(
                {'error': 'Company not found or access denied.'},
                status=status.HTTP_404_NOT_FOUND
            )

        features_dict = get_company_inventory_features(company)

        # Build a rich response with feature details
        all_features = InventoryFeature.objects.filter(is_active=True).order_by('display_order', 'name')
        result = []
        for feature in all_features:
            result.append({
                'id': str(feature.id),
                'code': feature.code,
                'name': feature.name,
                'description': feature.description,
                'icon': feature.icon,
                'route': feature.route,
                'display_order': feature.display_order,
                'enabled': features_dict.get(feature.code, True),
            })

        return Response({
            'company_id': str(company.id),
            'company_name': company.name,
            'features': result,
        })

    @action(detail=False, methods=['put'])
    def update_features(self, request):
        """
        PUT /api/inventory/company-features/
        Enable/disable features for the current company.

        Body:
        {
            "features": ["uuid1", "uuid2", ...],  # IDs of features to ENABLE
            "company": "optional-uuid"  # For admin to configure other companies
        }
        """
        serializer = CompanyFeatureToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company_id = serializer.validated_data.get('company')
        company = self.get_company(request, company_id)
        if not company:
            return Response(
                {'error': 'Company not found or access denied.'},
                status=status.HTTP_404_NOT_FOUND
            )

        enabled_ids = serializer.validated_data['features']
        all_features = InventoryFeature.objects.filter(is_active=True)

        results = []
        for feature in all_features:
            should_enable = str(feature.id) in [str(fid) for fid in enabled_ids]
            config, created = CompanyInventoryFeature.objects.update_or_create(
                company=company,
                inventory_feature=feature,
                defaults={'enabled': should_enable}
            )
            results.append({
                'feature_code': feature.code,
                'feature_name': feature.name,
                'enabled': should_enable,
            })

        return Response({
            'company_id': str(company.id),
            'company_name': company.name,
            'updated_features': results,
        })

    def retrieve(self, request, pk=None):
        """
        GET /api/inventory/company-features/{company_id}/
        View another company's configuration (admin only).
        """
        company = self.get_company(request, pk)
        if not company:
            return Response(
                {'error': 'Company not found or access denied.'},
                status=status.HTTP_404_NOT_FOUND
            )

        features_dict = get_company_inventory_features(company)
        all_features = InventoryFeature.objects.filter(is_active=True).order_by('display_order', 'name')
        result = []
        for feature in all_features:
            result.append({
                'id': str(feature.id),
                'code': feature.code,
                'name': feature.name,
                'icon': feature.icon,
                'route': feature.route,
                'display_order': feature.display_order,
                'enabled': features_dict.get(feature.code, True),
            })

        return Response({
            'company_id': str(company.id),
            'company_name': company.name,
            'features': result,
        })
