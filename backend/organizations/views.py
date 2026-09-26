from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Organization
from .serializers import OrganizationSerializer
from .services import create_organization_for_owner


class OrganizationListCreateView(ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True,
        ).distinct()

    def perform_create(self, serializer):
        organization = create_organization_for_owner(
            name=serializer.validated_data["name"],
            actor=self.request.user,
        )
        serializer.instance = organization
