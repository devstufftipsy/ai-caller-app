from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import os
import json
from google.cloud import texttospeech
from google.oauth2 import service_account
import uuid

app = Flask(__name__)

# A simple in-memory cache to hold generated audio clips
audio_cache = {}

# --- Initialize the Google TTS Client with credentials ---
try:
    credentials_json_str = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    credentials_info = json.loads(credentials_json_str)
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
except Exception as e:
    print(f"CRITICAL ERROR: Could not initialize Google TTS Client. {e}")
    tts_client = None


def get_google_audio(text_to_speak):
    """Gets the complete audio data from Google TTS."""
    if not tts_client:
        return None
    try:
        s_input = texttospeech.SynthesisInput(text=text_to_speak)
        voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Standard-C")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        
        audio_response = tts_client.synthesize_speech(input=s_input, voice=voice, audio_config=audio_config)
        return audio_response.audio_content
    except Exception as e:
        print(f"Error during TTS synthesis: {e}")
        return None

@app.route("/voice", methods=['POST'])
def voice():
    """Handles the conversation and serves TwiML."""
    response = VoiceResponse()
    
    # This is a test. In a real app, this would come from the LLM.
    ai_response = "Hello, this is a successful test of the Google Cloud Text-to-Speech API. The system is now fully operational."
    
    # Generate the audio and store it in our cache
    audio_data = get_google_audio(ai_response)
    
    if audio_data:
        clip_id = str(uuid.uuid4())
        audio_cache[clip_id] = audio_data
        
        # Point the <Play> verb to our new audio-playing endpoint
        audio_url = f"{request.host_url}play-audio/{clip_id}"
        response.play(audio_url)
    else:
        # Fallback if Google TTS fails
        response.say("My apologies, an error occurred with the voice service.", voice='alice')
        
    response.hangup()
    return str(response)

@app.route("/play-audio/<clip_id>")
def play_audio(clip_id):
    """Plays back the cached audio clip."""
    audio_data = audio_cache.pop(clip_id, None)
    if audio_data:
        return Response(audio_data, mimetype="audio/mpeg")
    return "Audio not found", 404

@app.route('/make-call')
def make_call():
    """Triggers the outbound call."""
    try:
        client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
        voice_url = f"{request.host_url}voice"
        
        call = client.calls.create(
            to=os.environ.get('MY_PHONE_NUMBER'),
            from_=os.environ.get('TWILIO_PHONE_NUMBER'),
            url=voice_url
        )
        return f"Success! Initiating final, stable test call. SID: {call.sid}"
    except Exception as e:
        return f"Error making call: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
