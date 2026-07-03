from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import (
    JobRequisition, Candidate, JobApplication,
    AppraisalCycle, PerformanceGoal, PerformanceReview,
    TrainingProgram, TrainingNomination,
    Resignation, ExitClearance
)
from .serializers_extended import (
    JobRequisitionSerializer, CandidateSerializer, JobApplicationSerializer,
    AppraisalCycleSerializer, PerformanceGoalSerializer, PerformanceReviewSerializer,
    TrainingProgramSerializer, TrainingNominationSerializer,
    ResignationSerializer, ExitClearanceSerializer
)

class JobRequisitionViewSet(viewsets.ModelViewSet):
    queryset = JobRequisition.objects.all()
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Auto-assign requested_by from current user's employee record"""
        try:
            employee = self.request.user.employee
            serializer.save(requested_by=employee)
        except Exception:
            raise

class CandidateViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.all()
    serializer_class = CandidateSerializer
    permission_classes = [IsAuthenticated]

class JobApplicationViewSet(viewsets.ModelViewSet):
    queryset = JobApplication.objects.all()
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]

class AppraisalCycleViewSet(viewsets.ModelViewSet):
    queryset = AppraisalCycle.objects.all()
    serializer_class = AppraisalCycleSerializer
    permission_classes = [IsAuthenticated]

class PerformanceGoalViewSet(viewsets.ModelViewSet):
    queryset = PerformanceGoal.objects.all()
    serializer_class = PerformanceGoalSerializer
    permission_classes = [IsAuthenticated]

class PerformanceReviewViewSet(viewsets.ModelViewSet):
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer
    permission_classes = [IsAuthenticated]

class TrainingProgramViewSet(viewsets.ModelViewSet):
    queryset = TrainingProgram.objects.all()
    serializer_class = TrainingProgramSerializer
    permission_classes = [IsAuthenticated]

class TrainingNominationViewSet(viewsets.ModelViewSet):
    queryset = TrainingNomination.objects.all()
    serializer_class = TrainingNominationSerializer
    permission_classes = [IsAuthenticated]

class ResignationViewSet(viewsets.ModelViewSet):
    queryset = Resignation.objects.all()
    serializer_class = ResignationSerializer
    permission_classes = [IsAuthenticated]

class ExitClearanceViewSet(viewsets.ModelViewSet):
    queryset = ExitClearance.objects.all()
    serializer_class = ExitClearanceSerializer
    permission_classes = [IsAuthenticated]
