from flask import Flask
from twilio.rest import Client
import os

app = Flask(__name__)

# Load credentials from Render's environment variables
ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
MY_PHONE_NUMBER = os.environ.get('MY_PHONE_NUMBER')

# This endpoint provides voice instructions AFTER the call connects.
@app.route("/voice", methods=['POST'])
def voice():
    from twilio.twiml.voice_response import VoiceResponse
    response = VoiceResponse()
    response.say("Hello. This is the AI agent calling. The outbound calling test is successful.", voice='alice')
    response.hangup()
    return str(response)

# This is the new "Go" button you will click to start the call.
@app.route('/make-call')
def make_call():
    try:
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        
        # The full URL for our /voice endpoint
        voice_url = "https://my-ai-caller-test.onrender.com/voice"

        # This command tells Twilio to make a call
        call = client.calls.create(
                                to=MY_PHONE_NUMBER,
                                from_=TWILIO_NUMBER,
                                url=voice_url # Points to our instructions
                            )
        return f"Success! Initiating a call to your number. Call SID: {call.sid}"
    except Exception as e:
        return f"Error making call: {str(e)}", 500

# This makes the app runnable
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
