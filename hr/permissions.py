from rest_framework import permissions


class HasHRRole(permissions.BasePermission):
    """
    Check that the user has one of the specified roles.
    Usage: HasHRRole(allowed_roles=['Superadmin', 'Admin'])
    """
    allowed_roles = ['Superadmin', 'Admin']

    def __init__(self, allowed_roles=None):
        if allowed_roles is not None:
            self.allowed_roles = allowed_roles

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in self.allowed_roles
        )


class IsHRAdmin(permissions.BasePermission):
    """
    Allow access only to HR Admin or Superadmin users
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin']
        )


class IsHRStaff(permissions.BasePermission):
    """
    Allow access to HR staff and HR Admin
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin']
        )


class IsPayrollExecutive(permissions.BasePermission):
    """
    Allow access only to payroll-related operations for designated users
    """
    def has_permission(self, request, view):
        # Can be extended to check for specific payroll role
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin']
        )


class IsManagerOrHR(permissions.BasePermission):
    """
    Allow managers to access their team's data, and HR to access all
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        # HR Admin has full access
        if request.user.role in ['Superadmin', 'Admin']:
            return True
        
        # Manager can access their own team
        if request.user.role == 'Manager':
            if hasattr(obj, 'employee'):
                return obj.employee.reporting_manager == request.user.employee
            if hasattr(obj, 'department'):
                return obj.department.manager == request.user.employee
        
        # Employee can access their own data
        if hasattr(obj, 'employee'):
            return obj.employee.user == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class IsEmployeeOrHR(permissions.BasePermission):
    """
    Employees can access their own data, HR can access all
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        # HR Admin has full access
        if request.user.role in ['Superadmin', 'Admin']:
            return True
        
        # Employee can access their own records
        if hasattr(obj, 'employee'):
            return obj.employee.user == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if isinstance(obj, type) and hasattr(obj, 'employee'):
            try:
                employee = request.user.employee
                return employee == obj.employee
            except:
                return False
        
        return False


class CanApproveLeave(permissions.BasePermission):
    """
    Only managers and HR can approve leaves
    """
    def has_permission(self, request, view):
        if request.method == 'GET':
            return True
        
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin', 'Manager']
        )
    
    def has_object_permission(self, request, view, obj):
        # HR can approve any leave
        if request.user.role in ['Superadmin', 'Admin']:
            return True
        
        # Manager can approve leaves of their team members
        if request.user.role == 'Manager':
            try:
                if obj.employee.reporting_manager.user == request.user:
                    return True
            except:
                pass
        
        return False


class CanProcessPayroll(permissions.BasePermission):
    """
    Only HR Admin and Payroll staff can process payroll
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin']
        )


class CanViewAttendance(permissions.BasePermission):
    """
    Managers can view their team's attendance, HR can view all, employees can view their own
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        # HR can view all
        if request.user.role in ['Superadmin', 'Admin']:
            return True
        
        # Managers can view their team
        if request.user.role == 'Manager':
            try:
                if obj.employee.reporting_manager.user == request.user:
                    return True
            except:
                pass
        
        # Employees can view their own records
        return obj.employee.user == request.user


class CanEditEmployeeData(permissions.BasePermission):
    """
    Only HR can edit employee master data
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin']
        )


class CanManageDocuments(permissions.BasePermission):
    """
    Employees can upload their documents, HR can manage all
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        # HR can manage any document
        if request.user.role in ['Superadmin', 'Admin']:
            return True
        
        # Employee can access their own documents
        return obj.employee.user == request.user


class IsFinanceOrHR(permissions.BasePermission):
    """
    Finance and HR roles for F&F settlement approvals
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin']
        )


class IsRecruitmentTeam(permissions.BasePermission):
    """
    Recruitment team access (HR staff with recruitment focus)
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['Superadmin', 'Admin']
        )
