# --- The Brain of Our Operation: app.py ---

from flask import Flask
from twilio.twiml.voice_response import VoiceResponse
import os

app = Flask(__name__)

# This is the endpoint Twilio will call when you answer the phone.
@app.route("/voice", methods=['POST'])
def voice():
    """This function generates the TwiML to speak a message."""
    # Create a new TwiML response object.
    response = VoiceResponse()

    # Use the <Say> verb to read a message.
    # We are using a basic voice here to keep the PoC simple and free.
    response.say("Hello. This is a successful test of the AI calling agent. The system is online.", voice='alice')

    # Hang up the call.
    response.hangup()

    return str(response)

# This line allows Render to run the Flask app.
if __name__ == '__main__':
    # Using port 10000 as is common for Render deployments.
    app.run(host='0.0.0.0', port=10000)