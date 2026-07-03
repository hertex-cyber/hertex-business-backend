from decimal import Decimal
from django.db.models import Sum
from sales_task_manager.models import (
    TargetCycle, SalesTarget, TargetLineItem, SalesTaskLog
)


class TargetEngine:
    """Core engine for target calculation and lifecycle management"""

    @staticmethod
    def calculate_achievement(target: SalesTarget) -> dict:
        """Calculate achieved amount from line items"""
        attained_items = target.line_items.filter(is_attained=True)
        achieved = attained_items.aggregate(
            total=Sum('actual_revenue')
        )['total'] or Decimal('0.00')

        return {
            'achieved_amount': achieved,
            'attainment_pct': round(
                float(achieved) / float(target.target_amount) * 100, 2
            ) if target.target_amount else 0,
            'attained_count': attained_items.count(),
            'total_items': target.line_items.count(),
        }

    @staticmethod
    def calculate_target_status(target: SalesTarget) -> str:
        """Determine target status based on achievement"""
        if target.target_amount == 0:
            return 'NOT_STARTED'

        ratio = float(target.achieved_amount) / float(target.target_amount)

        if ratio >= 1.1:
            return 'EXCEEDED'
        elif ratio >= 1.0:
            return 'ACHIEVED'
        elif ratio > 0:
            return 'IN_PROGRESS'
        else:
            return 'NOT_STARTED'

    @staticmethod
    def cascade_target_cycle(cycle: TargetCycle, user):
        """Close a target cycle and cascade finalisations"""
        if cycle.status != 'CLOSED':
            return {'error': 'Cycle must be in CLOSED status to finalise'}

        results = []
        for target in cycle.sales_targets.all():
            TargetEngine.finalise_target(target)
            results.append({
                'target_id': str(target.id),
                'status': target.status,
                'achieved': float(target.achieved_amount),
            })

            SalesTaskLog.objects.create(
                sales_target=target,
                user=user,
                activity_type='TARGET_UPDATED',
                description=f"Target finalised for cycle '{cycle.name}': {target.status}",
                metadata={
                    'achieved_amount': float(target.achieved_amount),
                    'target_amount': float(target.target_amount),
                    'status': target.status,
                }
            )

        return {'results': results}

    @staticmethod
    def update_achieved_from_invoice(invoice):
        """When an invoice is approved, update related target line items"""
        if not invoice.crm:
            return

        from sales_task_manager.models import TargetLineItem
        line_items = TargetLineItem.objects.filter(
            crm_deal=invoice.crm,
            is_attained=False
        )

        for item in line_items:
            item.is_attained = True
            item.attained_date = invoice.created_at.date() if hasattr(invoice, 'created_at') else None
            item.actual_revenue = invoice.amount if hasattr(invoice, 'amount') else item.expected_amount
            item.save()

            # Update parent target
            target = item.sales_target
            target.achieved_amount = sum(
                li.actual_revenue or 0
                for li in target.line_items.filter(is_attained=True)
            )
            target.status = TargetEngine.calculate_target_status(target)
            target.save()
