from rest_framework import viewsets, permissions
from payments.models import Payment
from payments.serializers import PaymentSerializer

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related('contact', 'crm', 'recorded_by')
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        contact_id = self.request.query_params.get('contact')
        crm_id = self.request.query_params.get('crm')
        
        if contact_id:
            qs = qs.filter(contact_id=contact_id)
        if crm_id:
            qs = qs.filter(crm_id=crm_id)
            
        return qs

    def perform_create(self, serializer):
        payment = serializer.save(recorded_by=self.request.user)
        
        # Log this payment activity in ContactLog
        from contacts.models import ContactLog
        description = f"Recorded payment of ₹{float(payment.amount):,.2f} for '{payment.payment_for}'"
        ContactLog.objects.create(
            contact=payment.contact,
            crm=payment.crm,
            activity_type='Payment Recorded',
            description=description,
            user=self.request.user
        )
