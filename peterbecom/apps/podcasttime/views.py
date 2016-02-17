from django.shortcuts import render


def index(request):
    context = {}
    context['page_title'] = "Podcast Time"
    return render(request, 'podcasttime/index.html', context)
