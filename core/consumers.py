import json

from asgiref.sync import async_to_sync as a2s
from channels.generic.websocket import JsonWebsocketConsumer


class ProgressConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.channel_name = self.scope['url_route']['kwargs']['id']
        print(f"connecting {id(self)}")

        # Join group
        a2s(self.channel_layer.group_add)(
            'progress_group',
            self.channel_name
        )

        self.accept()

    def disconnect(self, close_code):
        # Leave group
        a2s(self.channel_layer.group_discard)(
            'progress_group',
            self.channel_name
        )

    # Receive message from WebSocket
    def receive(self, data):
        message = text_data_json['message']

        # Send message to room group
        a2s(self.channel_layer.group_send)(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    # Receive message from room group
    def chat_message(self, event):
        message = event['message']

        # Send message to WebSocket
        self.send(text_data=json.dumps({
            'message': message
        }))
