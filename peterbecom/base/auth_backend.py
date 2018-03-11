import hashlib

from django.contrib.auth import get_user_model

UserModel = get_user_model()


def hash_email(email):
    return hashlib.md5(email).hexdigest()[:30]


class AuthBackend(object):
    """inspired by django_auth0.auth_backend.Auth0Backend"""

    def authenticate(self, request, **kwargs):
        try:
            email = kwargs.pop('email', None)
            username = kwargs.pop('nickname', None)
            if email:
                try:
                    user = UserModel.objects.get(
                        email__iexact=email
                    )
                except UserModel.DoesNotExist:
                    user = UserModel.objects.create(
                        email=email,
                        username=hash_email(email),
                    )
                if not user.username:
                    user.username = username
                    user.save()
                return user
        except Exception:
            import sys
            print(" **** WARNING **** ")
            print(sys.exc_info())
            print()
            raise

    def get_user(self, user_id):
        """
        Primary key identifier
        It is better to raise UserModel.DoesNotExist
        :param user_id:
        :return: UserModel instance
        """
        return UserModel._default_manager.get(pk=user_id)
