from django.db import models
from django.conf import settings
from core.models import Main
from contacts.models import Contact
from crm.models import CRM

PAYMENT_METHOD_CHOICES = (
    ('UPI', 'UPI'),
    ('Bank Transfer', 'Bank Transfer'),
    ('Cash', 'Cash'),
    ('Card', 'Card'),
    ('Net Banking', 'Net Banking'),
    ('Other', 'Other'),
)

class Payment(Main):
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name='payments'
    )
    crm = models.ForeignKey(
        CRM, on_delete=models.CASCADE, related_name='payments', null=True, blank=True
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_payments'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_for = models.CharField(max_length=255)
    remarks = models.TextField(blank=True, null=True)
    invoice = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(
        max_length=50, choices=PAYMENT_METHOD_CHOICES, default='UPI'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"₹{self.amount} - {self.payment_for} ({self.contact.name})"
