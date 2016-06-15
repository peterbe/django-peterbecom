from django.contrib.auth import get_user_model

UserModel = get_user_model()


class AuthBackend(object):
    """inspired by django_auth0.auth_backend.Auth0Backend"""

    def authenticate(self, **kwargs):
        try:
            email = kwargs.pop('email')
            username = kwargs.pop('nickname')
            print "KWARGS"
            from pprint import pprint
            pprint(kwargs)
            print ("EMAIL", email, "USERNAME", username)
            if email:
                try:
                    user = UserModel.objects.get(
                        email__iexact=email
                    )
                except UserModel.DoesNotExist:
                    user = UserModel.objects.create(
                        email=email,
                    )
                if not user.username:
                    user.username = username
                    user.save()
                return user
        except Exception:
            import sys
            print " **** WARNING **** "
            print sys.exc_info()
            print
            raise

    def get_user(self, user_id):
        """
        Primary key identifier
        It is better to raise UserModel.DoesNotExist
        :param user_id:
        :return: UserModel instance
        """
        return UserModel._default_manager.get(pk=user_id)
