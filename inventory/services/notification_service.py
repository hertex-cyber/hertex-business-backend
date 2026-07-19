"""
Inventory Notification Service
================================
Reusable notification service for inventory events.

Designed for use by:
- Stock Transfers
- Purchase Orders (future)
- Inventory Adjustments (future)
- Inventory Audits (future)
- Reservations (future)

All sends use fail_silently=True so a broken SMTP config never fails an API request.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q as Q


class InventoryNotificationService:
    """
    Generic notification service for inventory events.

    Usage:
        InventoryNotificationService.notify(
            event='transfer_created',
            subject="...",
            message="...",
            recipients=[user1, user2],
            context={...},
        )
    """

    @staticmethod
    def notify(event, subject, message, recipients, context=None):
        """
        Send email notification to a list of recipient users.

        Args:
            event: Event type string (e.g. 'transfer_created')
            subject: Email subject line
            message: Plain text email body
            recipients: List of User objects
            context: Optional dict with additional data for rendering
        """
        if not recipients:
            return

        emails = [
            u.email for u in recipients
            if u and u.email and getattr(u, 'is_active', True)
        ]
        if not emails:
            return

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=emails,
                fail_silently=True,
            )
        except Exception:
            pass

    @staticmethod
    def notify_event(event_name, transfer, extra_recipients=None):
        """
        Convenience method to notify relevant parties for a transfer event.

        Args:
            event_name: One of 'created', 'approved', 'rejected', 'dispatched', 'received'
            transfer: InventoryTransfer instance
            extra_recipients: Optional list of additional User objects
        """
        User = get_user_model()

        if event_name == 'created':
            # Notify admins/managers that a transfer needs approval
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=transfer.created_by_id if transfer.created_by else None)
            InventoryNotificationService.notify(
                event='transfer_created',
                subject=f"[Inventory] Transfer {transfer.transfer_number} Created",
                message=(
                    f"A new stock transfer has been created.\n\n"
                    f"Transfer #: {transfer.transfer_number}\n"
                    f"Type: {transfer.get_transfer_type_display()}\n"
                    f"Source: {transfer.source_location.location_name}\n"
                    f"Destination: {transfer.destination_location.location_name}\n"
                    f"Created by: {transfer.created_by.get_full_name() or transfer.created_by.email if transfer.created_by else 'Unknown'}\n"
                    f"Status: {transfer.get_status_display()}\n\n"
                    f"Please review and approve."
                ),
                recipients=list(admins),
            )

        elif event_name == 'approved':
            # Notify the creator that their transfer was approved
            recipients = [transfer.created_by] if transfer.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='transfer_approved',
                subject=f"[Inventory] Transfer {transfer.transfer_number} Approved",
                message=(
                    f"Your stock transfer has been approved.\n\n"
                    f"Transfer #: {transfer.transfer_number}\n"
                    f"Source: {transfer.source_location.location_name}\n"
                    f"Destination: {transfer.destination_location.location_name}\n"
                    f"Approved by: {transfer.approved_by.get_full_name() or transfer.approved_by.email if transfer.approved_by else 'System'}\n"
                    f"Notes: {transfer.approval_notes or 'N/A'}\n\n"
                    f"The transfer is now ready for dispatch."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'rejected':
            # Notify the creator that their transfer was rejected
            recipients = [transfer.created_by] if transfer.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='transfer_rejected',
                subject=f"[Inventory] Transfer {transfer.transfer_number} Rejected",
                message=(
                    f"Your stock transfer has been rejected.\n\n"
                    f"Transfer #: {transfer.transfer_number}\n"
                    f"Source: {transfer.source_location.location_name}\n"
                    f"Destination: {transfer.destination_location.location_name}\n"
                    f"Rejected by: {transfer.approved_by.get_full_name() or transfer.approved_by.email if transfer.approved_by else 'System'}\n"
                    f"Notes: {transfer.approval_notes or 'No remarks provided.'}\n\n"
                    f"Please revise and resubmit."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'dispatched':
            # Notify the destination location that stock is on its way
            User = get_user_model()
            destination_managers = User.objects.filter(
                is_active=True,
            ).filter(
                Q(managed_locations=transfer.destination_location) |
                Q(id=transfer.destination_location.manager_id)
            ).distinct()

            recipients = list(destination_managers)
            if transfer.created_by:
                recipients.append(transfer.created_by)
            if extra_recipients:
                recipients.extend(extra_recipients)

            InventoryNotificationService.notify(
                event='transfer_dispatched',
                subject=f"[Inventory] Transfer {transfer.transfer_number} Dispatched",
                message=(
                    f"Stock has been dispatched.\n\n"
                    f"Transfer #: {transfer.transfer_number}\n"
                    f"Source: {transfer.source_location.location_name}\n"
                    f"Destination: {transfer.destination_location.location_name}\n"
                    f"Dispatched at: {transfer.dispatched_at}\n\n"
                    f"Please prepare to receive the stock."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'received':
            # Notify the source location and creator that transfer was received
            recipients = [transfer.created_by] if transfer.created_by else []
            if transfer.received_by:
                recipients.append(transfer.received_by)
            if extra_recipients:
                recipients.extend(extra_recipients)

            status_text = transfer.get_status_display()
            InventoryNotificationService.notify(
                event='transfer_received',
                subject=f"[Inventory] Transfer {transfer.transfer_number} {status_text}",
                message=(
                    f"Stock transfer has been received.\n\n"
                    f"Transfer #: {transfer.transfer_number}\n"
                    f"Source: {transfer.source_location.location_name}\n"
                    f"Destination: {transfer.destination_location.location_name}\n"
                    f"Received by: {transfer.received_by.get_full_name() or transfer.received_by.email if transfer.received_by else 'Unknown'}\n"
                    f"Status: {status_text}\n\n"
                    f"The transfer is now complete."
                ),
                recipients=list(set(recipients)),
            )

    # =========================================================================
    # ADJUSTMENT EVENTS
    # =========================================================================

    @staticmethod
    def notify_adjustment_event(event_name, adjustment, extra_recipients=None):
        """
        Notify relevant parties for an adjustment event.

        Args:
            event_name: One of 'created', 'submitted', 'approved', 'rejected', 'applied'
            adjustment: InventoryAdjustment instance
            extra_recipients: Optional list of additional User objects
        """
        User = get_user_model()

        if event_name == 'created':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=adjustment.created_by_id if adjustment.created_by else None)
            InventoryNotificationService.notify(
                event='adjustment_created',
                subject=f"[Inventory] Adjustment {adjustment.adjustment_number} Created",
                message=(
                    f"A stock adjustment has been created.\n\n"
                    f"Adjustment #: {adjustment.adjustment_number}\n"
                    f"Type: {adjustment.get_adjustment_type_display()}\n"
                    f"Reason: {adjustment.reason.reason_name}\n"
                    f"Location: {adjustment.location.location_name}\n"
                    f"Created by: {adjustment.created_by.get_full_name() or adjustment.created_by.email if adjustment.created_by else 'Unknown'}\n"
                    f"Status: {adjustment.get_status_display()}\n\n"
                    f"Please review and approve."
                ),
                recipients=list(admins),
            )

        elif event_name == 'submitted':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=adjustment.created_by_id if adjustment.created_by else None)
            InventoryNotificationService.notify(
                event='adjustment_submitted',
                subject=f"[Inventory] Adjustment {adjustment.adjustment_number} Submitted for Approval",
                message=(
                    f"A stock adjustment has been submitted for approval.\n\n"
                    f"Adjustment #: {adjustment.adjustment_number}\n"
                    f"Type: {adjustment.get_adjustment_type_display()}\n"
                    f"Reason: {adjustment.reason.reason_name}\n"
                    f"Location: {adjustment.location.location_name}\n"
                    f"Submitted by: {adjustment.updated_by.get_full_name() or adjustment.updated_by.email if adjustment.updated_by else 'Unknown'}\n"
                    f"Items: {adjustment.items.count()}\n\n"
                    f"Please review and approve."
                ),
                recipients=list(admins),
            )

        elif event_name == 'approved':
            recipients = [adjustment.created_by] if adjustment.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='adjustment_approved',
                subject=f"[Inventory] Adjustment {adjustment.adjustment_number} Approved",
                message=(
                    f"Your stock adjustment has been approved.\n\n"
                    f"Adjustment #: {adjustment.adjustment_number}\n"
                    f"Location: {adjustment.location.location_name}\n"
                    f"Reason: {adjustment.reason.reason_name}\n"
                    f"Approved by: {adjustment.approved_by.get_full_name() or adjustment.approved_by.email if adjustment.approved_by else 'System'}\n"
                    f"Notes: {adjustment.approval_notes or 'N/A'}\n\n"
                    f"The adjustment is now ready to be applied."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'rejected':
            recipients = [adjustment.created_by] if adjustment.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='adjustment_rejected',
                subject=f"[Inventory] Adjustment {adjustment.adjustment_number} Rejected",
                message=(
                    f"Your stock adjustment has been rejected.\n\n"
                    f"Adjustment #: {adjustment.adjustment_number}\n"
                    f"Location: {adjustment.location.location_name}\n"
                    f"Reason: {adjustment.reason.reason_name}\n"
                    f"Rejected by: {adjustment.approved_by.get_full_name() or adjustment.approved_by.email if adjustment.approved_by else 'System'}\n"
                    f"Notes: {adjustment.approval_notes or 'No remarks provided.'}\n\n"
                    f"Please revise and resubmit."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'applied':
            recipients = [adjustment.created_by] if adjustment.created_by else []
            if adjustment.applied_by:
                recipients.append(adjustment.applied_by)
            if extra_recipients:
                recipients.extend(extra_recipients)

            InventoryNotificationService.notify(
                event='adjustment_applied',
                subject=f"[Inventory] Adjustment {adjustment.adjustment_number} Applied",
                message=(
                    f"Stock adjustment has been applied.\n\n"
                    f"Adjustment #: {adjustment.adjustment_number}\n"
                    f"Location: {adjustment.location.location_name}\n"
                    f"Reason: {adjustment.reason.reason_name}\n"
                    f"Type: {adjustment.get_adjustment_type_display()}\n"
                    f"Applied by: {adjustment.applied_by.get_full_name() or adjustment.applied_by.email if adjustment.applied_by else 'System'}\n"
                    f"Items affected: {adjustment.items.count()}\n\n"
                    f"Stock has been updated accordingly."
                ),
                recipients=list(set(recipients)),
            )

    # =========================================================================
    # RESERVATION EVENTS
    # =========================================================================

    @staticmethod
    def notify_reservation_event(event_name, reservation, extra_recipients=None):
        """
        Notify relevant parties for a reservation event.

        Args:
            event_name: One of 'created', 'activated', 'fulfilled', 'cancelled', 'expired'
            reservation: InventoryReservation instance
            extra_recipients: Optional list of additional User objects
        """
        User = get_user_model()

        if event_name == 'created':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=reservation.created_by_id if reservation.created_by else None)
            InventoryNotificationService.notify(
                event='reservation_created',
                subject=f"[Inventory] Reservation {reservation.reservation_number} Created",
                message=(
                    f"A new stock reservation has been created.\n\n"
                    f"Reservation #: {reservation.reservation_number}\n"
                    f"Type: {reservation.get_reservation_type_display()}\n"
                    f"Location: {reservation.source_location.location_name}\n"
                    f"Priority: {reservation.priority}\n"
                    f"Created by: {reservation.created_by.get_full_name() or reservation.created_by.email if reservation.created_by else 'Unknown'}\n"
                    f"Status: {reservation.get_status_display()}\n\n"
                    f"Please review and activate."
                ),
                recipients=list(admins),
            )

        elif event_name == 'activated':
            recipients = [reservation.created_by] if reservation.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='reservation_activated',
                subject=f"[Inventory] Reservation {reservation.reservation_number} Activated",
                message=(
                    f"Stock reservation has been activated.\n\n"
                    f"Reservation #: {reservation.reservation_number}\n"
                    f"Location: {reservation.source_location.location_name}\n"
                    f"Type: {reservation.get_reservation_type_display()}\n"
                    f"Status: {reservation.get_status_display()}\n\n"
                    f"Stock has been reserved."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'fulfilled':
            recipients = [reservation.created_by] if reservation.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='reservation_fulfilled',
                subject=f"[Inventory] Reservation {reservation.reservation_number} Fulfilled",
                message=(
                    f"Stock reservation has been fulfilled.\n\n"
                    f"Reservation #: {reservation.reservation_number}\n"
                    f"Location: {reservation.source_location.location_name}\n"
                    f"Status: {reservation.get_status_display()}\n\n"
                    f"Reserved stock has been released."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'cancelled':
            recipients = [reservation.created_by] if reservation.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='reservation_cancelled',
                subject=f"[Inventory] Reservation {reservation.reservation_number} Cancelled",
                message=(
                    f"Stock reservation has been cancelled.\n\n"
                    f"Reservation #: {reservation.reservation_number}\n"
                    f"Location: {reservation.source_location.location_name}\n"
                    f"Type: {reservation.get_reservation_type_display()}\n\n"
                    f"Reserved stock has been released."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'expired':
            recipients = [reservation.created_by] if reservation.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='reservation_expired',
                subject=f"[Inventory] Reservation {reservation.reservation_number} Expired",
                message=(
                    f"Stock reservation has expired.\n\n"
                    f"Reservation #: {reservation.reservation_number}\n"
                    f"Location: {reservation.source_location.location_name}\n"
                    f"Expired on: {reservation.updated_at}\n\n"
                    f"Reserved stock has been released."
                ),
                recipients=list(set(recipients)),
            )

    # =========================================================================
    # STOCK COUNT EVENTS (Section 9)
    # =========================================================================

    @staticmethod
    def notify_stock_count_event(event_name, stock_count, extra_recipients=None):
        """
        Notify relevant parties for a stock count event.

        Args:
            event_name: One of 'created', 'assigned', 'started', 'submitted',
                        'approved', 'completed', 'cancelled'
            stock_count: InventoryStockCount instance
            extra_recipients: Optional list of additional User objects
        """
        User = get_user_model()

        if event_name == 'created':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=stock_count.created_by_id if stock_count.created_by else None)
            InventoryNotificationService.notify(
                event='stock_count_created',
                subject=f"[Inventory] Stock Count {stock_count.count_number} Created",
                message=(
                    f"A new physical stock count has been created.\n\n"
                    f"Count #: {stock_count.count_number}\n"
                    f"Type: {stock_count.get_count_type_display()}\n"
                    f"Location: {stock_count.location.location_name}\n"
                    f"Reason: {stock_count.reason.reason_name}\n"
                    f"Created by: {stock_count.created_by.get_full_name() or stock_count.created_by.email if stock_count.created_by else 'Unknown'}\n"
                    f"Items to count: {stock_count.items.count()}\n"
                    f"Status: {stock_count.get_status_display()}\n\n"
                    f"Please assign counters and begin counting."
                ),
                recipients=list(admins),
            )

            # Also notify assigned counters
            counters = list(stock_count.assigned_counters.all())
            if counters:
                InventoryNotificationService.notify(
                    event='stock_count_assigned_to_you',
                    subject=f"[Inventory] You've been assigned to stock count {stock_count.count_number}",
                    message=(
                        f"You have been assigned to a physical stock count.\n\n"
                        f"Count #: {stock_count.count_number}\n"
                        f"Type: {stock_count.get_count_type_display()}\n"
                        f"Location: {stock_count.location.location_name}\n"
                        f"Reason: {stock_count.reason.reason_name}\n"
                        f"Items to count: {stock_count.items.count()}\n\n"
                        f"Please begin counting."
                    ),
                    recipients=counters,
                )

        elif event_name == 'assigned':
            counters = list(stock_count.assigned_counters.all())
            if counters:
                InventoryNotificationService.notify(
                    event='stock_count_assigned',
                    subject=f"[Inventory] Counters assigned to stock count {stock_count.count_number}",
                    message=(
                        f"Counters have been assigned to a physical stock count.\n\n"
                        f"Count #: {stock_count.count_number}\n"
                        f"Location: {stock_count.location.location_name}\n"
                        f"Status: {stock_count.get_status_display()}\n\n"
                        f"Please begin counting."
                    ),
                    recipients=counters,
                )

        elif event_name == 'started':
            recipients = [stock_count.created_by] if stock_count.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='stock_count_started',
                subject=f"[Inventory] Stock Count {stock_count.count_number} Started",
                message=(
                    f"Physical stock counting has started.\n\n"
                    f"Count #: {stock_count.count_number}\n"
                    f"Location: {stock_count.location.location_name}\n"
                    f"Status: {stock_count.get_status_display()}\n\n"
                    f"Counters are now counting items."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'submitted':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=stock_count.updated_by_id if stock_count.updated_by else None)
            InventoryNotificationService.notify(
                event='stock_count_submitted',
                subject=f"[Inventory] Stock Count {stock_count.count_number} Submitted for Approval",
                message=(
                    f"A physical stock count has been submitted for approval.\n\n"
                    f"Count #: {stock_count.count_number}\n"
                    f"Location: {stock_count.location.location_name}\n"
                    f"Items counted: {stock_count.total_items_counted}\n"
                    f"Type: {stock_count.get_count_type_display()}\n"
                    f"Submitted by: {stock_count.updated_by.get_full_name() or stock_count.updated_by.email if stock_count.updated_by else 'Unknown'}\n\n"
                    f"Please review and approve."
                ),
                recipients=list(admins),
            )

        elif event_name == 'approved':
            recipients = [stock_count.created_by] if stock_count.created_by else []
            for counter in stock_count.assigned_counters.all():
                recipients.append(counter)
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='stock_count_approved',
                subject=f"[Inventory] Stock Count {stock_count.count_number} Approved",
                message=(
                    f"Physical stock count has been approved.\n\n"
                    f"Count #: {stock_count.count_number}\n"
                    f"Location: {stock_count.location.location_name}\n"
                    f"Approved by: {stock_count.approved_by.get_full_name() or stock_count.approved_by.email if stock_count.approved_by else 'System'}\n"
                    f"Notes: {stock_count.approval_notes or 'N/A'}\n\n"
                    f"The count is now being processed to generate adjustments."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'completed':
            recipients = [stock_count.created_by] if stock_count.created_by else []
            if stock_count.completed_by:
                recipients.append(stock_count.completed_by)
            if extra_recipients:
                recipients.extend(extra_recipients)

            adj_ref = f"Adjustment: {stock_count.generated_adjustment.adjustment_number}" if stock_count.generated_adjustment else "No adjustment generated"

            InventoryNotificationService.notify(
                event='stock_count_completed',
                subject=f"[Inventory] Stock Count {stock_count.count_number} Completed",
                message=(
                    f"Physical stock count has been completed.\n\n"
                    f"Count #: {stock_count.count_number}\n"
                    f"Location: {stock_count.location.location_name}\n"
                    f"Total items counted: {stock_count.total_items_counted}\n"
                    f"Items with differences: {stock_count.total_items_with_difference}\n"
                    f"Total difference value: {stock_count.total_difference_value}\n"
                    f"Completed by: {stock_count.completed_by.get_full_name() or stock_count.completed_by.email if stock_count.completed_by else 'System'}\n"
                    f"{adj_ref}\n\n"
                    f"Stock has been updated accordingly."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'cancelled':
            recipients = [stock_count.created_by] if stock_count.created_by else []
            for counter in stock_count.assigned_counters.all():
                recipients.append(counter)
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='stock_count_cancelled',
                subject=f"[Inventory] Stock Count {stock_count.count_number} Cancelled",
                message=(
                    f"Physical stock count has been cancelled.\n\n"
                    f"Count #: {stock_count.count_number}\n"
                    f"Location: {stock_count.location.location_name}\n"
                    f"Reason: {stock_count.reason.reason_name}\n"
                    f"Status: {stock_count.get_status_display()}"
                ),
                recipients=list(set(recipients)),
            )

    # =========================================================================
    # PURCHASE ORDER EVENTS (Section 10)
    # =========================================================================

    @staticmethod
    def notify_purchase_event(event_name, purchase_order, extra_recipients=None):
        """
        Notify relevant parties for a purchase order event.

        Args:
            event_name: One of 'created', 'sent', 'received', 'closed', 'cancelled'
            purchase_order: PurchaseOrder instance
            extra_recipients: Optional list of additional User objects
        """
        User = get_user_model()

        if event_name == 'created':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=purchase_order.created_by_id if purchase_order.created_by else None)
            InventoryNotificationService.notify(
                event='purchase_order_created',
                subject=f"[Inventory] Purchase Order {purchase_order.order_number} Created",
                message=(
                    f"A new purchase order has been created.\n\n"
                    f"PO #: {purchase_order.order_number}\n"
                    f"Order Date: {purchase_order.order_date}\n"
                    f"Supplier: {purchase_order.supplier_name or (purchase_order.supplier.name if purchase_order.supplier else 'N/A')}\n"
                    f"Total Amount: {purchase_order.total_amount}\n"
                    f"Created by: {purchase_order.created_by.get_full_name() or purchase_order.created_by.email if purchase_order.created_by else 'Unknown'}\n"
                    f"Status: {purchase_order.get_status_display()}\n\n"
                    f"Please review and send to the supplier."
                ),
                recipients=list(admins),
            )

        elif event_name == 'sent':
            recipients = [purchase_order.created_by] if purchase_order.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='purchase_order_sent',
                subject=f"[Inventory] Purchase Order {purchase_order.order_number} Sent to Supplier",
                message=(
                    f"Purchase order has been sent to the supplier.\n\n"
                    f"PO #: {purchase_order.order_number}\n"
                    f"Supplier: {purchase_order.supplier_name or (purchase_order.supplier.name if purchase_order.supplier else 'N/A')}\n"
                    f"Total Amount: {purchase_order.total_amount}\n"
                    f"Sent at: {purchase_order.sent_at}\n\n"
                    f"Awaiting receipt of goods."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'received':
            recipients = [purchase_order.created_by] if purchase_order.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='purchase_order_received',
                subject=f"[Inventory] Purchase Order {purchase_order.order_number} Received",
                message=(
                    f"Goods have been received against purchase order.\n\n"
                    f"PO #: {purchase_order.order_number}\n"
                    f"Supplier: {purchase_order.supplier_name or (purchase_order.supplier.name if purchase_order.supplier else 'N/A')}\n"
                    f"Status: {purchase_order.get_status_display()}\n\n"
                    f"Stock has been updated in the ledger."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'closed':
            recipients = [purchase_order.created_by] if purchase_order.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='purchase_order_closed',
                subject=f"[Inventory] Purchase Order {purchase_order.order_number} Closed",
                message=(
                    f"Purchase order has been closed.\n\n"
                    f"PO #: {purchase_order.order_number}\n"
                    f"Supplier: {purchase_order.supplier_name or (purchase_order.supplier.name if purchase_order.supplier else 'N/A')}\n"
                    f"Closed at: {purchase_order.closed_at}\n\n"
                    f"All items have been fully received."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'cancelled':
            recipients = [purchase_order.created_by] if purchase_order.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='purchase_order_cancelled',
                subject=f"[Inventory] Purchase Order {purchase_order.order_number} Cancelled",
                message=(
                    f"Purchase order has been cancelled.\n\n"
                    f"PO #: {purchase_order.order_number}\n"
                    f"Supplier: {purchase_order.supplier_name or (purchase_order.supplier.name if purchase_order.supplier else 'N/A')}\n"
                    f"Status: {purchase_order.get_status_display()}"
                ),
                recipients=list(set(recipients)),
            )

    # =========================================================================
    # GOODS RECEIPT NOTE EVENTS (Section 11)
    # =========================================================================

    @staticmethod
    def notify_grn_event(event_name, grn, extra_recipients=None):
        """
        Notify relevant parties for a GRN event.

        Args:
            event_name: One of 'created', 'submitted', 'approved', 'received', 'completed', 'cancelled'
            grn: InventoryGoodsReceipt instance
            extra_recipients: Optional list of additional User objects
        """
        User = get_user_model()

        if event_name == 'created':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=grn.created_by_id if grn.created_by else None)
            InventoryNotificationService.notify(
                event='grn_created',
                subject=f"[Inventory] GRN {grn.grn_number} Created",
                message=(
                    f"A new Goods Receipt Note has been created.\n\n"
                    f"GRN #: {grn.grn_number}\n"
                    f"PO #: {grn.purchase_order.order_number}\n"
                    f"Supplier: {grn.supplier_name or (grn.supplier.name if grn.supplier else 'N/A')}\n"
                    f"Location: {grn.location.location_name if grn.location else 'N/A'}\n"
                    f"Date: {grn.receipt_date}\n"
                    f"Created by: {grn.created_by.get_full_name() or grn.created_by.email if grn.created_by else 'Unknown'}\n"
                    f"Status: {grn.get_status_display()}\n\n"
                    f"Please review and submit for approval."
                ),
                recipients=list(admins),
            )

        elif event_name == 'submitted':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=grn.updated_by_id if grn.updated_by else None)
            InventoryNotificationService.notify(
                event='grn_submitted',
                subject=f"[Inventory] GRN {grn.grn_number} Submitted for Approval",
                message=(
                    f"A Goods Receipt Note has been submitted for approval.\n\n"
                    f"GRN #: {grn.grn_number}\n"
                    f"PO #: {grn.purchase_order.order_number}\n"
                    f"Supplier: {grn.supplier_name or (grn.supplier.name if grn.supplier else 'N/A')}\n"
                    f"Submitted by: {grn.updated_by.get_full_name() or grn.updated_by.email if grn.updated_by else 'Unknown'}\n"
                    f"Items: {grn.items.count()}\n\n"
                    f"Please review and approve."
                ),
                recipients=list(admins),
            )

        elif event_name == 'approved':
            recipients = [grn.created_by] if grn.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='grn_approved',
                subject=f"[Inventory] GRN {grn.grn_number} Approved",
                message=(
                    f"Goods Receipt Note has been approved.\n\n"
                    f"GRN #: {grn.grn_number}\n"
                    f"PO #: {grn.purchase_order.order_number}\n"
                    f"Approved by: {grn.approved_by.get_full_name() or grn.approved_by.email if grn.approved_by else 'System'}\n"
                    f"Notes: {grn.approval_notes or 'N/A'}\n\n"
                    f"The GRN is now ready for receiving."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'received':
            recipients = [grn.created_by] if grn.created_by else []
            if grn.received_by:
                recipients.append(grn.received_by)
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='grn_received',
                subject=f"[Inventory] GRN {grn.grn_number} Received",
                message=(
                    f"Goods have been received against the GRN.\n\n"
                    f"GRN #: {grn.grn_number}\n"
                    f"PO #: {grn.purchase_order.order_number}\n"
                    f"Received by: {grn.received_by.get_full_name() or grn.received_by.email if grn.received_by else 'Unknown'}\n"
                    f"Received at: {grn.received_at}\n"
                    f"Status: {grn.get_status_display()}\n\n"
                    f"Stock has been updated in the ledger."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'completed':
            recipients = [grn.created_by] if grn.created_by else []
            if grn.received_by:
                recipients.append(grn.received_by)
            if grn.completed_by:
                recipients.append(grn.completed_by)
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='grn_completed',
                subject=f"[Inventory] GRN {grn.grn_number} Completed",
                message=(
                    f"Goods Receipt Note has been completed.\n\n"
                    f"GRN #: {grn.grn_number}\n"
                    f"PO #: {grn.purchase_order.order_number}\n"
                    f"Completed by: {grn.completed_by.get_full_name() or grn.completed_by.email if grn.completed_by else 'System'}\n"
                    f"Status: {grn.get_status_display()}\n\n"
                    f"The GRN process is now complete."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'cancelled':
            recipients = [grn.created_by] if grn.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='grn_cancelled',
                subject=f"[Inventory] GRN {grn.grn_number} Cancelled",
                message=(
                    f"Goods Receipt Note has been cancelled.\n\n"
                    f"GRN #: {grn.grn_number}\n"
                    f"PO #: {grn.purchase_order.order_number}\n"
                    f"Status: {grn.get_status_display()}"
                ),
                recipients=list(set(recipients)),
            )

    # =========================================================================
    # SUPPLIER INVOICE EVENTS (Section 12)
    # =========================================================================

    @staticmethod
    def notify_supplier_invoice_event(event_name, invoice, extra_recipients=None):
        """
        Notify relevant parties for a supplier invoice event.

        Args:
            event_name: One of 'created', 'submitted', 'approved', 'posted',
                       'payment_recorded', 'paid', 'cancelled', 'voided'
            invoice: InventorySupplierInvoice instance
            extra_recipients: Optional list of additional User objects
        """
        User = get_user_model()

        if event_name == 'created':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=invoice.created_by_id if invoice.created_by else None)
            InventoryNotificationService.notify(
                event='supplier_invoice_created',
                subject=f"[Inventory] Supplier Invoice {invoice.invoice_number} Created",
                message=(
                    f"A new supplier invoice has been created.\n\n"
                    f"Invoice #: {invoice.invoice_number}\n"
                    f"Supplier: {invoice.supplier_name or (invoice.supplier.name if invoice.supplier else 'N/A')}\n"
                    f"Amount: {invoice.grand_total}\n"
                    f"Date: {invoice.invoice_date}\n"
                    f"Due Date: {invoice.due_date or 'N/A'}\n"
                    f"Created by: {invoice.created_by.get_full_name() or invoice.created_by.email if invoice.created_by else 'Unknown'}\n"
                    f"Status: {invoice.get_status_display()}\n\n"
                    f"Please review and submit for approval."
                ),
                recipients=list(admins),
            )

        elif event_name == 'submitted':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=invoice.updated_by_id if invoice.updated_by else None)
            InventoryNotificationService.notify(
                event='supplier_invoice_submitted',
                subject=f"[Inventory] Supplier Invoice {invoice.invoice_number} Submitted for Approval",
                message=(
                    f"A supplier invoice has been submitted for approval.\n\n"
                    f"Invoice #: {invoice.invoice_number}\n"
                    f"Supplier: {invoice.supplier_name or (invoice.supplier.name if invoice.supplier else 'N/A')}\n"
                    f"Amount: {invoice.grand_total}\n"
                    f"Submitted by: {invoice.updated_by.get_full_name() or invoice.updated_by.email if invoice.updated_by else 'Unknown'}\n"
                    f"Items: {invoice.items.count()}\n\n"
                    f"Please review and approve."
                ),
                recipients=list(admins),
            )

        elif event_name == 'approved':
            recipients = [invoice.created_by] if invoice.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='supplier_invoice_approved',
                subject=f"[Inventory] Supplier Invoice {invoice.invoice_number} Approved",
                message=(
                    f"Supplier invoice has been approved.\n\n"
                    f"Invoice #: {invoice.invoice_number}\n"
                    f"Supplier: {invoice.supplier_name or (invoice.supplier.name if invoice.supplier else 'N/A')}\n"
                    f"Amount: {invoice.grand_total}\n"
                    f"Approved by: {invoice.approved_by.get_full_name() or invoice.approved_by.email if invoice.approved_by else 'System'}\n"
                    f"Notes: {invoice.approval_notes or 'N/A'}\n\n"
                    f"The invoice is now ready to be posted."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'posted':
            recipients = [invoice.created_by] if invoice.created_by else []
            if invoice.approved_by:
                recipients.append(invoice.approved_by)
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='supplier_invoice_posted',
                subject=f"[Inventory] Supplier Invoice {invoice.invoice_number} Posted",
                message=(
                    f"Supplier invoice has been posted.\n\n"
                    f"Invoice #: {invoice.invoice_number}\n"
                    f"Supplier: {invoice.supplier_name or (invoice.supplier.name if invoice.supplier else 'N/A')}\n"
                    f"Amount: {invoice.grand_total}\n"
                    f"Posted by: {invoice.posted_by.get_full_name() or invoice.posted_by.email if invoice.posted_by else 'System'}\n\n"
                    f"The invoice is now payable."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'payment_recorded':
            recipients = [invoice.created_by] if invoice.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            status_text = invoice.get_payment_status_display()
            InventoryNotificationService.notify(
                event='supplier_invoice_payment',
                subject=f"[Inventory] Payment Recorded for Invoice {invoice.invoice_number}",
                message=(
                    f"A payment has been recorded against supplier invoice.\n\n"
                    f"Invoice #: {invoice.invoice_number}\n"
                    f"Supplier: {invoice.supplier_name or (invoice.supplier.name if invoice.supplier else 'N/A')}\n"
                    f"Outstanding: {invoice.outstanding_amount}\n"
                    f"Payment Status: {status_text}\n\n"
                    f"The invoice is now {status_text}."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'cancelled':
            recipients = [invoice.created_by] if invoice.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='supplier_invoice_cancelled',
                subject=f"[Inventory] Supplier Invoice {invoice.invoice_number} Cancelled",
                message=(
                    f"Supplier invoice has been cancelled.\n\n"
                    f"Invoice #: {invoice.invoice_number}\n"
                    f"Supplier: {invoice.supplier_name or (invoice.supplier.name if invoice.supplier else 'N/A')}\n"
                    f"Status: {invoice.get_status_display()}"
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'voided':
            recipients = [invoice.created_by] if invoice.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='supplier_invoice_voided',
                subject=f"[Inventory] Supplier Invoice {invoice.invoice_number} Voided",
                message=(
                    f"Supplier invoice has been voided.\n\n"
                    f"Invoice #: {invoice.invoice_number}\n"
                    f"Supplier: {invoice.supplier_name or (invoice.supplier.name if invoice.supplier else 'N/A')}\n"
                    f"Amount: {invoice.grand_total}\n\n"
                    f"This invoice has been voided and is no longer payable."
                ),
                recipients=list(set(recipients)),
            )

    # =========================================================================
    # SUPPLIER PAYMENT EVENTS (Section 14)
    # =========================================================================

    @staticmethod
    def notify_supplier_payment_event(event_name, payment, extra_recipients=None):
        """
        Notify relevant parties for a supplier payment event.

        Args:
            event_name: One of 'created', 'submitted', 'approved', 'posted',
                       'completed', 'cancelled', 'voided'
            payment: InventorySupplierPayment instance
            extra_recipients: Optional list of additional User objects
        """
        User = get_user_model()

        if event_name == 'created':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=payment.created_by_id if payment.created_by else None)
            InventoryNotificationService.notify(
                event='supplier_payment_created',
                subject=f"[Inventory] Supplier Payment {payment.payment_number} Created",
                message=(
                    f"A new supplier payment has been created.\n\n"
                    f"Payment #: {payment.payment_number}\n"
                    f"Date: {payment.payment_date}\n"
                    f"Supplier: {payment.supplier_name or (payment.supplier.name if payment.supplier else 'N/A')}\n"
                    f"Amount: {payment.total_amount}\n"
                    f"Method: {payment.payment_method}\n"
                    f"Created by: {payment.created_by.get_full_name() or payment.created_by.email if payment.created_by else 'Unknown'}\n"
                    f"Status: {payment.get_status_display()}\n\n"
                    f"Please review and submit for approval."
                ),
                recipients=list(admins),
            )

        elif event_name == 'submitted':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=payment.updated_by_id if payment.updated_by else None)
            InventoryNotificationService.notify(
                event='supplier_payment_submitted',
                subject=f"[Inventory] Supplier Payment {payment.payment_number} Submitted for Approval",
                message=(
                    f"A supplier payment has been submitted for approval.\n\n"
                    f"Payment #: {payment.payment_number}\n"
                    f"Supplier: {payment.supplier_name or (payment.supplier.name if payment.supplier else 'N/A')}\n"
                    f"Amount: {payment.total_amount}\n"
                    f"Submitted by: {payment.updated_by.get_full_name() or payment.updated_by.email if payment.updated_by else 'Unknown'}\n\n"
                    f"Please review and approve."
                ),
                recipients=list(admins),
            )

        elif event_name == 'approved':
            recipients = [payment.created_by] if payment.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='supplier_payment_approved',
                subject=f"[Inventory] Supplier Payment {payment.payment_number} Approved",
                message=(
                    f"Supplier payment has been approved.\n\n"
                    f"Payment #: {payment.payment_number}\n"
                    f"Supplier: {payment.supplier_name or (payment.supplier.name if payment.supplier else 'N/A')}\n"
                    f"Amount: {payment.total_amount}\n"
                    f"Approved by: {payment.approved_by.get_full_name() or payment.approved_by.email if payment.approved_by else 'System'}\n"
                    f"Notes: {payment.approval_notes or 'N/A'}\n\n"
                    f"The payment is now ready to be posted."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'posted':
            recipients = [payment.created_by] if payment.created_by else []
            if payment.approved_by:
                recipients.append(payment.approved_by)
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='supplier_payment_posted',
                subject=f"[Inventory] Supplier Payment {payment.payment_number} Posted",
                message=(
                    f"Supplier payment has been posted.\n\n"
                    f"Payment #: {payment.payment_number}\n"
                    f"Supplier: {payment.supplier_name or (payment.supplier.name if payment.supplier else 'N/A')}\n"
                    f"Amount: {payment.total_amount}\n"
                    f"Posted by: {payment.posted_by.get_full_name() or payment.posted_by.email if payment.posted_by else 'System'}\n\n"
                    f"Invoice balances have been updated."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'completed':
            recipients = [payment.created_by] if payment.created_by else []
            if payment.posted_by:
                recipients.append(payment.posted_by)
            if payment.completed_by:
                recipients.append(payment.completed_by)
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='supplier_payment_completed',
                subject=f"[Inventory] Supplier Payment {payment.payment_number} Completed",
                message=(
                    f"Supplier payment has been completed.\n\n"
                    f"Payment #: {payment.payment_number}\n"
                    f"Supplier: {payment.supplier_name or (payment.supplier.name if payment.supplier else 'N/A')}\n"
                    f"Amount: {payment.total_amount}\n"
                    f"Completed by: {payment.completed_by.get_full_name() or payment.completed_by.email if payment.completed_by else 'System'}\n\n"
                    f"The payment process is now complete."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'cancelled':
            recipients = [payment.created_by] if payment.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='supplier_payment_cancelled',
                subject=f"[Inventory] Supplier Payment {payment.payment_number} Cancelled",
                message=(
                    f"Supplier payment has been cancelled.\n\n"
                    f"Payment #: {payment.payment_number}\n"
                    f"Supplier: {payment.supplier_name or (payment.supplier.name if payment.supplier else 'N/A')}\n"
                    f"Status: {payment.get_status_display()}"
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'voided':
            recipients = [payment.created_by] if payment.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='supplier_payment_voided',
                subject=f"[Inventory] Supplier Payment {payment.payment_number} Voided",
                message=(
                    f"Supplier payment has been voided.\n\n"
                    f"Payment #: {payment.payment_number}\n"
                    f"Supplier: {payment.supplier_name or (payment.supplier.name if payment.supplier else 'N/A')}\n"
                    f"Amount: {payment.total_amount}\n\n"
                    f"All invoice allocations have been reversed."
                ),
                recipients=list(set(recipients)),
            )

    # =========================================================================
    # PURCHASE RETURN EVENTS (Section 13)
    # =========================================================================

    @staticmethod
    def notify_purchase_return_event(event_name, return_obj, extra_recipients=None):
        """
        Notify relevant parties for a purchase return event.

        Args:
            event_name: One of 'created', 'submitted', 'approved', 'rejected',
                       'returned', 'completed', 'cancelled'
            return_obj: InventoryPurchaseReturn instance
            extra_recipients: Optional list of additional User objects
        """
        User = get_user_model()

        if event_name == 'created':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=return_obj.created_by_id if return_obj.created_by else None)
            InventoryNotificationService.notify(
                event='purchase_return_created',
                subject=f"[Inventory] Purchase Return {return_obj.return_number} Created",
                message=(
                    f"A new purchase return has been created.\n\n"
                    f"Return #: {return_obj.return_number}\n"
                    f"Date: {return_obj.return_date}\n"
                    f"Supplier: {return_obj.supplier_name or (return_obj.supplier.name if return_obj.supplier else 'N/A')}\n"
                    f"Reason: {return_obj.return_reason or 'N/A'}\n"
                    f"Total Amount: {return_obj.total_amount}\n"
                    f"Created by: {return_obj.created_by.get_full_name() or return_obj.created_by.email if return_obj.created_by else 'Unknown'}\n"
                    f"Status: {return_obj.get_status_display()}\n\n"
                    f"Please review and submit for approval."
                ),
                recipients=list(admins),
            )

        elif event_name == 'submitted':
            admins = User.objects.filter(
                role__in=['Admin', 'Manager'],
                is_active=True,
            ).exclude(id=return_obj.updated_by_id if return_obj.updated_by else None)
            InventoryNotificationService.notify(
                event='purchase_return_submitted',
                subject=f"[Inventory] Purchase Return {return_obj.return_number} Submitted for Approval",
                message=(
                    f"A purchase return has been submitted for approval.\n\n"
                    f"Return #: {return_obj.return_number}\n"
                    f"Supplier: {return_obj.supplier_name or (return_obj.supplier.name if return_obj.supplier else 'N/A')}\n"
                    f"Total Amount: {return_obj.total_amount}\n"
                    f"Submitted by: {return_obj.updated_by.get_full_name() or return_obj.updated_by.email if return_obj.updated_by else 'Unknown'}\n"
                    f"Items: {return_obj.items.count()}\n\n"
                    f"Please review and approve."
                ),
                recipients=list(admins),
            )

        elif event_name == 'approved':
            recipients = [return_obj.created_by] if return_obj.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='purchase_return_approved',
                subject=f"[Inventory] Purchase Return {return_obj.return_number} Approved",
                message=(
                    f"Purchase return has been approved.\n\n"
                    f"Return #: {return_obj.return_number}\n"
                    f"Supplier: {return_obj.supplier_name or (return_obj.supplier.name if return_obj.supplier else 'N/A')}\n"
                    f"Total Amount: {return_obj.total_amount}\n"
                    f"Approved by: {return_obj.approved_by.get_full_name() or return_obj.approved_by.email if return_obj.approved_by else 'System'}\n"
                    f"Notes: {return_obj.approval_notes or 'N/A'}\n\n"
                    f"The return is now ready to be processed."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'rejected':
            recipients = [return_obj.created_by] if return_obj.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='purchase_return_rejected',
                subject=f"[Inventory] Purchase Return {return_obj.return_number} Rejected",
                message=(
                    f"Purchase return has been rejected.\n\n"
                    f"Return #: {return_obj.return_number}\n"
                    f"Supplier: {return_obj.supplier_name or (return_obj.supplier.name if return_obj.supplier else 'N/A')}\n"
                    f"Rejected by: {return_obj.approved_by.get_full_name() or return_obj.approved_by.email if return_obj.approved_by else 'System'}\n"
                    f"Notes: {return_obj.approval_notes or 'No remarks provided.'}\n\n"
                    f"Please revise and resubmit."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'returned':
            recipients = [return_obj.created_by] if return_obj.created_by else []
            if return_obj.processed_by:
                recipients.append(return_obj.processed_by)
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='purchase_return_returned',
                subject=f"[Inventory] Purchase Return {return_obj.return_number} Returned to Supplier",
                message=(
                    f"Goods have been returned to supplier.\n\n"
                    f"Return #: {return_obj.return_number}\n"
                    f"Supplier: {return_obj.supplier_name or (return_obj.supplier.name if return_obj.supplier else 'N/A')}\n"
                    f"Returned by: {return_obj.processed_by.get_full_name() or return_obj.processed_by.email if return_obj.processed_by else 'System'}\n"
                    f"Returned at: {return_obj.processed_at}\n"
                    f"Status: {return_obj.get_status_display()}\n\n"
                    f"Stock has been updated in the ledger."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'completed':
            recipients = [return_obj.created_by] if return_obj.created_by else []
            if return_obj.completed_by:
                recipients.append(return_obj.completed_by)
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='purchase_return_completed',
                subject=f"[Inventory] Purchase Return {return_obj.return_number} Completed",
                message=(
                    f"Purchase return has been completed.\n\n"
                    f"Return #: {return_obj.return_number}\n"
                    f"Supplier: {return_obj.supplier_name or (return_obj.supplier.name if return_obj.supplier else 'N/A')}\n"
                    f"Total Amount: {return_obj.total_amount}\n"
                    f"Completed by: {return_obj.completed_by.get_full_name() or return_obj.completed_by.email if return_obj.completed_by else 'System'}\n\n"
                    f"The return process is now complete."
                ),
                recipients=list(set(recipients)),
            )

        elif event_name == 'cancelled':
            recipients = [return_obj.created_by] if return_obj.created_by else []
            if extra_recipients:
                recipients.extend(extra_recipients)
            InventoryNotificationService.notify(
                event='purchase_return_cancelled',
                subject=f"[Inventory] Purchase Return {return_obj.return_number} Cancelled",
                message=(
                    f"Purchase return has been cancelled.\n\n"
                    f"Return #: {return_obj.return_number}\n"
                    f"Supplier: {return_obj.supplier_name or (return_obj.supplier.name if return_obj.supplier else 'N/A')}\n"
                    f"Status: {return_obj.get_status_display()}"
                ),
                recipients=list(set(recipients)),
            )
