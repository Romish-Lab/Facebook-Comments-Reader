# reader/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('fetch-posts', views.fetch_posts, name='fetch_posts'),
    path('start-monitoring', views.start_monitoring, name='start_monitoring'),
    path('stop-monitoring', views.stop_monitoring, name='stop_monitoring'),
    
    # ⭐️ ADD THESE TWO NEW URLS ⭐️
    path('post/<str:post_id>/dashboard/', views.comment_dashboard, name='comment_dashboard'),
    path('keywords/', views.manage_keywords, name='manage_keywords'),
]