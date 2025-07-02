from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import os
import json
from google.cloud import texttospeech
from google.oauth2 import service_account # Import the service_account module
import base64

app = Flask(__name__)

# --- This is the fix ---
# Manually load the credentials from the environment variable.
try:
    # Get the JSON string from the environment variable
    credentials_json_str = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    # Parse the JSON string into a dictionary
    credentials_info = json.loads(credentials_json_str)
    # Create credentials from the dictionary
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    # Initialize the client with the explicit credentials
    tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
except Exception as e:
    print(f"CRITICAL ERROR: Could not initialize Google TTS Client. {e}")
    tts_client = None


@app.route("/voice", methods=['POST'])
def voice():
    """This function generates the voice response using Google TTS."""
    response = VoiceResponse()

    text_to_speak = "Hello, and welcome. This is a successful test of the Google Cloud Text-to-Speech API. The system is now fully operational."

    # Check if the TTS client was initialized successfully
    if not tts_client:
        response.say("There is a critical configuration error with the voice service.", voice='alice')
        response.hangup()
        return str(response)

    try:
        voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Standard-C", ssml_gender=texttospeech.SsmlVoiceGender.FEMALE)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        synthesis_input = texttospeech.SynthesisInput(text=text_to_speak)
        audio_response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

        audio_base64 = base64.b64encode(audio_response.audio_content).decode('utf-8')
        audio_data_uri = f"data:audio/mpeg;base64,{audio_base64}"

        response.play(audio_data_uri)
        response.hangup()
    except Exception as e:
        print(f"Error during TTS synthesis: {e}")
        response.say("An error occurred while generating the voice response.", voice='alice')
        response.hangup()

    return str(response)

@app.route('/make-call')
def make_call():
    """Triggers the outbound call."""
    try:
        client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
        host_url = request.host_url
        voice_url = f"{host_url}voice"

        call = client.calls.create(
            to=os.environ.get('MY_PHONE_NUMBER'),
            from_=os.environ.get('TWILIO_PHONE_NUMBER'),
            url=voice_url
        )
        return f"Success! Initiating final test call. SID: {call.sid}"
    except Exception as e:
        return f"Error making call: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
