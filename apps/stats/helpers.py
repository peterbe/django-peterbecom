from jingo import register


@register.function
def thousands(v):
    return format(v, ',')
