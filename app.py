from flask import Flask, request, Response
from groq import Groq
import os
import httpx
import json
from google.cloud import texttospeech
from google.oauth2 import service_account
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import uuid

app = Flask(__name__)
audio_cache = {}

# --- Initialize Google TTS Client with credentials ---
try:
    credentials_json_str = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    credentials_info = json.loads(credentials_json_str)
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
except Exception as e:
    print(f"CRITICAL ERROR: Could not initialize Google TTS Client. {e}")
    tts_client = None

# --- PERSONAS Dictionary ---
PERSONAS = {
    "marketing": "You are 'Alex', a friendly marketing agent for 'Pixel Perfect'. Your goal is to see if the user is interested in a free trial of a new AI-powered photo editing software. Keep your responses short and natural.",
    "sales": "You are 'Sam', a direct sales representative for 'Pixel Perfect'. Your goal is to qualify the user and book a demo. You are persuasive and results-oriented.",
    "lead_gen": "You are 'Jordan', a cheerful lead generation specialist for 'Pixel Perfect'. Your primary goal is to verify contact information and confirm interest in AI photo editing tools."
}

# --- New: VOICES Dictionary with Google Voice Names ---
VOICES = {
    "female1": "en-US-Standard-C", # A standard female voice
    "male1": "en-US-Standard-D",   # A standard male voice
    "female2": "en-US-Wavenet-F",  # A more natural WaveNet voice
    "male2": "en-US-Wavenet-E"   # A more natural WaveNet voice
}

def get_google_audio(text_to_speak, voice_name="en-US-Standard-C"):
    """Gets the complete audio data from Google TTS using a specific voice."""
    if not tts_client: return None
    try:
        s_input = texttospeech.SynthesisInput(text=text_to_speak)
        voice = texttospeech.VoiceSelectionParams(language_code="en-US", name=voice_name)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        audio_response = tts_client.synthesize_speech(input=s_input, voice=voice, audio_config=audio_config)
        return audio_response.audio_content
    except Exception as e:
        print(f"Error during TTS synthesis: {e}")
        return None

@app.route("/voice", methods=['POST'])
def voice():
    persona_key = request.cookies.get('persona', 'marketing')
    voice_name = request.cookies.get('voice_name', VOICES['female1'])
    user_name = request.cookies.get('user_name', 'the user')

    system_prompt = PERSONAS.get(persona_key, PERSONAS['marketing']).format(user_name=user_name)
    speech_result = request.form.get('SpeechResult', '').strip()
    conversation = request.cookies.get('conversation', system_prompt)

    if speech_result: conversation += f"\n\nUser: {speech_result}"

    try:
        groq_client = Groq(api_key=os.environ.get('GROQ_API_KEY'), http_client=httpx.Client(proxies=""))
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": conversation}, {"role": "user", "content": speech_result or f"Hello, I'm calling for {user_name}."}],
            model="llama3-8b-8192",
        )
        ai_response = chat_completion.choices[0].message.content.strip()
        conversation += f"\n\nAI: {ai_response}"
    except Exception as e:
        ai_response = "I'm sorry, I'm having a connection issue. Could you say that again?"
        print(f"Error calling Groq: {e}")

    response = VoiceResponse()
    audio_data = get_google_audio(ai_response, voice_name)
    if audio_data:
        clip_id = str(uuid.uuid4())
        audio_cache[clip_id] = audio_data
        audio_url = f"{request.host_url}play-audio/{clip_id}"
        gather = response.gather(input='speech', action='/voice', speechTimeout='auto', model='phone_call')
        gather.play(audio_url)
    else:
        gather = response.gather(input='speech', action='/voice', speechTimeout='5')
        gather.say("My apologies, my voice service is having an issue.", voice='alice')

    response.redirect('/voice')

    resp = app.make_response(str(response))
    resp.set_cookie('conversation', conversation)
    resp.set_cookie('user_name', user_name)
    resp.set_cookie('persona', persona_key)
    resp.set_cookie('voice_name', voice_name)
    return resp

@app.route("/play-audio/<clip_id>")
def play_audio(clip_id):
    audio_data = audio_cache.pop(clip_id, None)
    if audio_data: return Response(audio_data, mimetype="audio/mpeg")
    return "Audio not found", 404

@app.route('/make-call/<persona>/<voice_name>/<user_name>')
def make_call(persona, voice_name, user_name):
    try:
        if persona not in PERSONAS: return "Invalid persona", 404
        gcp_voice_name = VOICES.get(voice_name.lower())
        if not gcp_voice_name: return "Invalid voice name. Use female1, male1, female2, or male2.", 404

        client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
        voice_url = f"{request.host_url}voice"
        call = client.calls.create(to=os.environ.get('MY_PHONE_NUMBER'), from_=os.environ.get('TWILIO_PHONE_NUMBER'), url=voice_url)

        resp = app.make_response(f"Success! Initiating call to {user_name} with persona '{persona}' and voice '{voice_name}'.")
        resp.set_cookie('user_name', user_name)
        resp.set_cookie('persona', persona)
        resp.set_cookie('voice_name', gcp_voice_name)
        resp.set_cookie('conversation', expires=0)
        return resp
    except Exception as e:
        return f"Error making call: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
