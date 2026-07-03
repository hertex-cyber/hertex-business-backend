from rest_framework import serializers
from .models import (
    JobRequisition, Candidate, JobApplication,
    AppraisalCycle, PerformanceGoal, PerformanceReview,
    TrainingProgram, TrainingNomination,
    Resignation, ExitClearance
)

class JobRequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobRequisition
        fields = '__all__'

class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = '__all__'

class JobApplicationSerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source='candidate.first_name', read_only=True)
    requisition_title = serializers.CharField(source='requisition.designation.name', read_only=True)

    class Meta:
        model = JobApplication
        fields = '__all__'

class AppraisalCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppraisalCycle
        fields = '__all__'

class PerformanceGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceGoal
        fields = '__all__'

class PerformanceReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceReview
        fields = '__all__'

class TrainingProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingProgram
        fields = '__all__'

class TrainingNominationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingNomination
        fields = '__all__'

class ResignationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resignation
        fields = '__all__'

class ExitClearanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExitClearance
        fields = '__all__'
