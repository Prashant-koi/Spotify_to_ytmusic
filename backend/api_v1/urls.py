from django.urls import path
from . import views

urlpatterns = [
    path('spotify/authorize/', views.spotify_authorize, name='spotify_authorize'),
    path('spotify/callback/', views.spotify_callback, name='spotify_callback'),
    path('ytmusic/authorize/', views.ytmusic_authorize, name='ytmusic_authorize'),
    path('ytmusic/callback/', views.ytmusic_callback, name='ytmusic_callback'),
    path('transfer/', views.transfer_playlist, name='transfer_playlist'),
]