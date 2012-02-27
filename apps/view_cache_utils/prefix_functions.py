
auth_key_prefixes = {True:'logged_in', False:'not_logged_in'}

def auth_key_prefix(request):
    ''' key prefix for exactly 2 versions of page: for authenticated and for anonymous users.
    '''
    if request.GET:
        return None #magic value to disable caching
    res = auth_key_prefixes[request.user.is_authenticated()]
    return res