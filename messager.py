import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv

load_dotenv()

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure

class Texter(Client):
    def __init__(self):
        super().__init__(os.environ.get('TWILIO_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
        self.phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
        self.area_code = '+1'
        self.messaging_service_sid = os.environ.get('TWILIO_MS_SID')

    def send_text(self, message, to_phone_number):
        try:
            print("sending text")
            message = self.messages.create(
                messaging_service_sid=self.messaging_service_sid,
                body=message,
                to=f'{self.area_code}{to_phone_number}'
            )
            print("message: ", message)
        except TwilioRestException as e:
            print(f"error sending: {e}")
            return f"ERROR: {e}"
        return message

if __name__ == '__main__':
    # good for testing - really high standard testing :/
    texter = Texter()
    print(texter.send_text('hello hello', '333'))