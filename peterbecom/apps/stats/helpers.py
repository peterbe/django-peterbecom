from jingo import register


@register.function
def thousands(n):
    return format(n, ',')
