# WebSocket routing table

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf.urls import url

from core import consumers


websocket_urlpatterns = [
    url(r'^ws/progress/(?P<id>[^/]+)/$', consumers.ProgressConsumer),
]

application = ProtocolTypeRouter({
    # Empty for now (http->django views is added by default)
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})


