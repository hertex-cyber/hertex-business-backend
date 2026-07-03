from rest_framework import serializers
from crm.models import CRM, Pipeline, Stage
from contacts.serializers import ContactSerializer
from authentication.serializers import DepartmentSerializer, UserSerializer
from authentication.models import Department


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = ['id', 'pipeline', 'name', 'slug', 'order', 'color']
        read_only_fields = ['id', 'slug', 'pipeline']


class PipelineSerializer(serializers.ModelSerializer):
    stages = StageSerializer(many=True, read_only=True)
    departments = DepartmentSerializer(many=True, read_only=True)
    department_ids = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='departments',
        many=True,
        required=False,
        write_only=True
    )

    class Meta:
        model = Pipeline
        fields = ['id', 'name', 'description', 'stages', 'departments', 'department_ids', 'assignment_type', 'mandatory_fields', 'custom_fields_enabled', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class CRMSerializer(serializers.ModelSerializer):
    contact_details = ContactSerializer(source='contact', read_only=True)
    pipeline_details = PipelineSerializer(source='pipeline', read_only=True)
    stage_details = StageSerializer(source='stage', read_only=True)
    assigned_user_details = UserSerializer(source='assigned_user', read_only=True)

    class Meta:
        model = CRM
        fields = [
            'id', 'contact', 'contact_details',
            'pipeline', 'pipeline_details',
            'stage', 'stage_details',
            'assigned_user', 'assigned_user_details',
            'value', 'priority', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
