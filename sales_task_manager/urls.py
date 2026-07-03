from django.urls import path, include
from rest_framework.routers import DefaultRouter
from sales_task_manager.views import (
    TargetCycleViewSet, SalesTargetViewSet, TargetLineItemViewSet,
    SalesProgrammeViewSet, ProgrammeMilestoneViewSet, SalesTaskViewSet,
    TaskDependencyViewSet, TaskTimeLogViewSet,
    ProgrammeResourceAllocationViewSet, TargetAssignmentRuleViewSet,
    TaskAttachmentViewSet, SalesTaskLogViewSet, DashboardViewSet
)

router = DefaultRouter()
router.register(r'target-cycles', TargetCycleViewSet, basename='target-cycles')
router.register(r'targets', SalesTargetViewSet, basename='targets')
router.register(r'target-line-items', TargetLineItemViewSet, basename='target-line-items')
router.register(r'programmes', SalesProgrammeViewSet, basename='programmes')
router.register(r'milestones', ProgrammeMilestoneViewSet, basename='milestones')
router.register(r'tasks', SalesTaskViewSet, basename='tasks')
router.register(r'task-dependencies', TaskDependencyViewSet, basename='task-dependencies')
router.register(r'time-logs', TaskTimeLogViewSet, basename='time-logs')
router.register(r'resource-allocations', ProgrammeResourceAllocationViewSet, basename='resource-allocations')
router.register(r'assignment-rules', TargetAssignmentRuleViewSet, basename='assignment-rules')
router.register(r'task-attachments', TaskAttachmentViewSet, basename='task-attachments')
router.register(r'activity-logs', SalesTaskLogViewSet, basename='activity-logs')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
