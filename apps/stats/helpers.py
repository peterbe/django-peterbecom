from jingo import register


@register.function
def thousands(n):
    # if only this was python 2.7!! :(
    #return format(n, ',')
    r = []
    for i, c in enumerate(reversed(str(n))):
        if i and (not (i % 3)):
            r.insert(0, ',')
        r.insert(0, c)
    return ''.join(r)
