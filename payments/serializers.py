from rest_framework import serializers
from payments.models import Payment
from contacts.serializers import ContactSerializer

class PaymentSerializer(serializers.ModelSerializer):
    contact_details = ContactSerializer(source='contact', read_only=True)
    recorded_by_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'contact', 'contact_details',
            'crm', 'recorded_by', 'recorded_by_details',
            'amount', 'payment_for', 'remarks',
            'invoice', 'payment_method',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'recorded_by_details']

    def get_recorded_by_details(self, obj):
        if obj.recorded_by:
            return {
                'id': obj.recorded_by.id,
                'first_name': obj.recorded_by.first_name,
                'last_name': obj.recorded_by.last_name,
                'email': obj.recorded_by.email
            }
        return None
