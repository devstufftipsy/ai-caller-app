from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import os
import json
from google.cloud import texttospeech
import base64

app = Flask(__name__)

# Initialize the Google TTS Client
# The client will automatically find and use the credentials we set in Render.
tts_client = texttospeech.TextToSpeechClient()

@app.route("/voice", methods=['POST'])
def voice():
    """This function generates the voice response using Google TTS."""
    response = VoiceResponse()

    # The text our agent will say.
    text_to_speak = "Hello, and welcome. This is a successful test of the Google Cloud Text-to-Speech API. The system is now fully operational."

    # Set up the voice configuration
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Generate the audio from Google
    synthesis_input = texttospeech.SynthesisInput(text=text_to_speak)
    audio_response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # To play the audio without needing another URL, we encode it
    # and embed it directly in the instruction for Twilio.
    audio_base64 = base64.b64encode(audio_response.audio_content).decode('utf-8')
    audio_data_uri = f"data:audio/mpeg;base64,{audio_base64}"

    # Play the embedded audio
    response.play(audio_data_uri)
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
