from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from sales_task_manager.models import (
    SalesTarget, TargetAssignmentRule, SalesTask, SalesTaskLog
)
from sales_task_manager.services.task_generator import TaskGenerator


@receiver(post_save, sender='crm.CRM')
def on_deal_created(sender, instance, created, **kwargs):
    """When a new deal is added, check for auto-generation rules"""
    if created:
        _trigger_deal_rules(instance, 'DEAL_CREATED')


@receiver(pre_save, sender='crm.CRM')
def on_deal_stage_changing(sender, instance, **kwargs):
    """When a deal stage changes, check for stage-change task rules"""
    if instance.pk:
        try:
            from crm.models import CRM
            old = CRM.objects.get(pk=instance.pk)
            if old.stage_id != instance.stage_id:
                # Store old stage on instance for post_save to use
                instance._old_stage_id = old.stage_id
        except CRM.DoesNotExist:
            pass


@receiver(post_save, sender='crm.CRM')
def on_deal_stage_changed(sender, instance, created, **kwargs):
    """Post-save handler for stage changes"""
    if not created and hasattr(instance, '_old_stage_id'):
        _trigger_deal_rules(instance, 'DEAL_STAGE_CHANGE')


def _trigger_deal_rules(deal, trigger_type):
    """Find matching active rules and generate tasks"""
    generator = TaskGenerator()

    # Find targets that have this deal as a line item
    from sales_task_manager.models import TargetLineItem
    line_items = TargetLineItem.objects.filter(crm_deal=deal)

    for line_item in line_items:
        target = line_item.sales_target
        if target and target.cycle.status == 'ACTIVE':
            active_rules = target.assignment_rules.filter(
                trigger=trigger_type,
                is_active=True
            )
            for rule in active_rules:
                generator.generate_from_rule(rule, deal=deal)
