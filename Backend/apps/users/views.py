from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.users.models import User
from apps.users.serializers import RegisterSerializer, UserSerializer


class RegisterAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)


class MeAPIView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user
