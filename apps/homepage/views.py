import datetime
from django.shortcuts import render
from apps.plog.models import Category, BlogItem, BlogComment

def home(request):
    data = {}
    data['blogitems'] =  (
      BlogItem.objects
      .filter(pub_date__lt=datetime.datetime.utcnow())
      .order_by('-pub_date')
    )[:10]

    return render(request, 'homepage/home.html', data)
