from rest_framework import serializers
from inventory.models import InventoryFeature, CompanyInventoryFeature


class InventoryFeatureSerializer(serializers.ModelSerializer):
    """Serializer for the master list of inventory features."""

    class Meta:
        model = InventoryFeature
        fields = [
            'id', 'code', 'name', 'description', 'icon',
            'route', 'display_order', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InventoryFeatureListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for feature dropdowns/references."""

    class Meta:
        model = InventoryFeature
        fields = ['id', 'code', 'name', 'icon', 'route', 'display_order']


class CompanyInventoryFeatureSerializer(serializers.ModelSerializer):
    """Serializer for company-specific feature toggles."""
    feature_code = serializers.CharField(
        source='inventory_feature.code', read_only=True
    )
    feature_name = serializers.CharField(
        source='inventory_feature.name', read_only=True
    )
    feature_icon = serializers.CharField(
        source='inventory_feature.icon', read_only=True
    )
    feature_route = serializers.CharField(
        source='inventory_feature.route', read_only=True
    )
    feature_display_order = serializers.IntegerField(
        source='inventory_feature.display_order', read_only=True
    )
    company_name = serializers.CharField(
        source='company.name', read_only=True
    )

    class Meta:
        model = CompanyInventoryFeature
        fields = [
            'id', 'company', 'company_name',
            'inventory_feature', 'feature_code', 'feature_name',
            'feature_icon', 'feature_route', 'feature_display_order',
            'enabled',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompanyFeatureToggleSerializer(serializers.Serializer):
    """Serializer for bulk enabling/disabling features."""
    features = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        help_text="List of InventoryFeature IDs to enable. All others will be disabled."
    )

    company = serializers.UUIDField(required=False, allow_null=True)
