from rest_framework import permissions


class IsSalesManager(permissions.BasePermission):
    """Manager role — can assign tasks, manage programmes, view team data"""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin', 'Manager']
        )


class IsSalesAdmin(permissions.BasePermission):
    """Admin/Superadmin — full access to all data and configuration"""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin']
        )


class IsTaskOwnerOrManager(permissions.BasePermission):
    """Object-level: task owner, their manager, or admin"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # Admin has full access
        if request.user.role in ['Superadmin', 'Admin']:
            return True

        # Manager can access their team's tasks
        if request.user.role == 'Manager':
            if hasattr(obj, 'assigned_to') and obj.assigned_to:
                try:
                    if obj.assigned_to.supervisor == request.user:
                        return True
                except Exception:
                    pass
            return True  # Managers can see all tasks in their scope

        # Staff can only access their own tasks
        if hasattr(obj, 'assigned_to'):
            return obj.assigned_to == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user

        return False


class CanAssignTasks(permissions.BasePermission):
    """Only managers and above can assign tasks to others"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin', 'Manager']
        )


class CanManageProgrammes(permissions.BasePermission):
    """Managers+ can manage programmes, staff can view"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin', 'Manager']
        )


class CanManageConfig(permissions.BasePermission):
    """Only Admin/Superadmin can manage configuration (assignment rules, cycles)"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin']
        )
