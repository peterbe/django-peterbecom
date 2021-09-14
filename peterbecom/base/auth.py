from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from peterbecom.base.models import UserProfile


class AuthenticationBackend(OIDCAuthenticationBackend):
    def create_user(self, claims):
        email = claims.get("email")
        username = self.get_username(claims)
        user = self.UserModel.objects.create_user(username, email=email)

        self._create_or_set_user_profile(user, claims)
        return user

    def update_user(self, user, claims):
        self._create_or_set_user_profile(user, claims)
        return user

    def _create_or_set_user_profile(self, user, claims):
        for user_profile in UserProfile.objects.filter(user=user):
            user_profile.claims = claims
            user_profile.save()
            break
        else:
            UserProfile.objects.create(
                user=user,
                claims=claims,
            )
