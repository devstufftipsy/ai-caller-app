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

# --- Initialize Google TTS Client ---
try:
    credentials_json_str = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    credentials_info = json.loads(credentials_json_str)
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
except Exception as e:
    print(f"CRITICAL ERROR: Could not initialize Google TTS Client. {e}")
    tts_client = None

SYSTEM_PROMPT_TEMPLATE = """
You are 'Alex', a friendly and professional marketing agent for 'Pixel Perfect'.
Your goal is to speak with {user_name} about a free trial of a new AI-powered photo editing software.
Keep your responses very short, natural, and conversational, like a real human on a phone call.
Never say you are an AI.
"""

def get_google_audio(text_to_speak):
    if not tts_client: return None
    try:
        s_input = texttospeech.SynthesisInput(text=text_to_speak)
        voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Standard-C", ssml_gender=texttospeech.SsmlVoiceGender.FEMALE)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        audio_response = tts_client.synthesize_speech(input=s_input, voice=voice, audio_config=audio_config)
        return audio_response.audio_content
    except Exception as e:
        print(f"Error during TTS synthesis: {e}")
        return None

@app.route("/voice", methods=['POST'])
def voice():
    user_name = request.cookies.get('user_name', 'the user')
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(user_name=user_name)
    speech_result = request.form.get('SpeechResult', '').strip()
    conversation = request.cookies.get('conversation', system_prompt)

    if speech_result:
        conversation += f"\n\nUser: {speech_result}"

    try:
        groq_client = Groq(api_key=os.environ.get('GROQ_API_KEY'), http_client=httpx.Client(proxies=""))
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": conversation}, {"role": "user", "content": speech_result or "Hello"}],
            model="llama3-8b-8192",
        )
        ai_response = chat_completion.choices[0].message.content.strip()
        conversation += f"\n\nAI: {ai_response}"
    except Exception as e:
        ai_response = "I'm sorry, I seem to be having a connection issue. Could you say that again?"
        print(f"Error calling Groq: {e}")

    response = VoiceResponse()
    audio_data = get_google_audio(ai_response)
    if audio_data:
        clip_id = str(uuid.uuid4())
        audio_cache[clip_id] = audio_data
        audio_url = f"{request.host_url}play-audio/{clip_id}"
        gather = response.gather(input='speech', action='/voice', speechTimeout='auto', enhanced="true")
        gather.play(audio_url)
    else:
        gather = response.gather(input='speech', action='/voice', speechTimeout='auto')
        gather.say("My apologies, my voice service is having an issue. Could you say that again?", voice='alice')

    response.redirect('/voice')

    resp = app.make_response(str(response))
    resp.set_cookie('conversation', conversation)
    resp.set_cookie('user_name', user_name)
    return resp

@app.route("/play-audio/<clip_id>")
def play_audio(clip_id):
    audio_data = audio_cache.pop(clip_id, None)
    if audio_data:
        return Response(audio_data, mimetype="audio/mpeg")
    return "Audio not found", 404

@app.route('/make-call/<user_name>')
def make_call(user_name):
    try:
        client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
        voice_url = f"{request.host_url}voice"
        call = client.calls.create(to=os.environ.get('MY_PHONE_NUMBER'), from_=os.environ.get('TWILIO_PHONE_NUMBER'), url=voice_url)
        resp = app.make_response(f"Success! Initiating call to {user_name}. SID: {call.sid}")
        resp.set_cookie('user_name', user_name)
        resp.set_cookie('conversation', expires=0)
        return resp
    except Exception as e:
        return f"Error making call: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
