"""
Decorators and mixins for blocking inventory feature routes that are disabled
for the current company. Returns 403 Forbidden with a clear error message.

Usage:
    from inventory.feature_decorators import require_inventory_feature

    @require_inventory_feature('items')
    def my_view(request):
        ...

    # Or as a viewset mixin:
    from inventory.feature_decorators import InventoryFeatureMixin

    class MyViewSet(InventoryFeatureMixin, viewsets.ModelViewSet):
        required_feature = 'items'
"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status

from inventory.feature_helpers import is_inventory_feature_enabled


def require_inventory_feature(feature_code):
    """
    Decorator that checks if an inventory feature is enabled for the
    current user's company. Returns 403 if disabled.

    Usage:
        @require_inventory_feature('supplier_invoices')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view_instance, request, *args, **kwargs):
            company = getattr(request.user, 'organization', None)
            if company and not is_inventory_feature_enabled(company, feature_code):
                return Response(
                    {'error': 'Inventory feature disabled.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return view_func(view_instance, request, *args, **kwargs)
        return _wrapped_view
    return decorator


class InventoryFeatureMixin:
    """
    Mixin for class-based views / ViewSets that require a specific
    inventory feature to be enabled.

    Set `required_feature` on the viewset:
        class SupplierInvoiceViewSet(InventoryFeatureMixin, viewsets.ModelViewSet):
            required_feature = 'supplier_invoices'
            ...
    """

    required_feature = None

    def initial(self, request, *args, **kwargs):
        """Check feature before processing the request."""
        if self.required_feature:
            company = getattr(request.user, 'organization', None)
            if company and not is_inventory_feature_enabled(company, self.required_feature):
                self.permission_denied(
                    request,
                    message='Inventory feature disabled.',
                    code=status.HTTP_403_FORBIDDEN,
                )
        super().initial(request, *args, **kwargs)
