"""
Reusable helper functions for checking inventory feature availability.

These helpers are designed to be reusable later when the same pattern
is extended to Sales, CRM, HR, Finance, etc. without major refactoring.

Usage:
    from inventory.feature_helpers import is_inventory_feature_enabled

    if is_inventory_feature_enabled(company, 'items'):
        # show items
"""

from inventory.models import CompanyInventoryFeature, InventoryFeature


def get_company_inventory_features(company):
    """
    Return a dict of feature_code -> enabled for a given company.

    If a feature has no CompanyInventoryFeature record yet, it defaults
    to the feature's is_active field.

    Returns:
        dict: {'dashboard': True, 'items': True, 'supplier_invoices': False, ...}
    """
    features = InventoryFeature.objects.filter(is_active=True)
    company_configs = {
        cfg.inventory_feature_id: cfg.enabled
        for cfg in CompanyInventoryFeature.objects.filter(company=company)
    }

    result = {}
    for feature in features:
        if feature.id in company_configs:
            result[feature.code] = company_configs[feature.id]
        else:
            # Default to feature's global is_active setting
            result[feature.code] = feature.is_active

    return result


def is_inventory_feature_enabled(company, feature_code):
    """
    Check if a specific inventory feature is enabled for a company.

    Args:
        company: Organization instance
        feature_code: str, e.g. 'items', 'transfers', 'supplier_invoices'

    Returns:
        bool: True if the feature is enabled
    """
    try:
        feature = InventoryFeature.objects.get(code=feature_code)
    except InventoryFeature.DoesNotExist:
        return False

    try:
        config = CompanyInventoryFeature.objects.get(
            company=company,
            inventory_feature=feature
        )
        return config.enabled
    except CompanyInventoryFeature.DoesNotExist:
        return feature.is_active


def get_enabled_feature_codes(company):
    """
    Return a list of feature codes that are enabled for the company.

    Useful for filtering sidebar navigation, generating menus, etc.
    """
    features = get_company_inventory_features(company)
    return [code for code, enabled in features.items() if enabled]
