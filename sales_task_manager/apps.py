from django.apps import AppConfig


class SalesTaskManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sales_task_manager'
    verbose_name = 'Sales Task Manager'

    def ready(self):
        import sales_task_manager.signals  # noqa
