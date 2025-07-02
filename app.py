from flask import Flask, request, Response
from groq import Groq
import os
import httpx
from urllib.parse import quote
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import uuid # Used to create unique IDs for our audio clips

app = Flask(__name__)

# A simple in-memory cache to hold the generated audio clips
audio_cache = {}

SYSTEM_PROMPT_TEMPLATE = """
You are 'Alex', a friendly and professional marketing agent for 'Pixel Perfect'.
Your goal is to speak with {user_name} about a free trial of a new AI-powered photo editing software.
Keep your responses very short, natural, and conversational, like a real human on a phone call.
Never say you are an AI.
"""

def get_elevenlabs_audio(text_to_speak):
    """Gets the complete audio data from ElevenLabs, not a stream."""
    ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
    VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
    
    # Using the standard, non-streaming endpoint
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = { "Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY }
    data = { "text": text_to_speak, "model_id": "eleven_monolingual_v1", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75} }

    try:
        response = httpx.post(url, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.content # Return the raw audio bytes
        else:
            print(f"ElevenLabs Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error getting ElevenLabs audio: {e}")
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
        client = Groq(api_key=os.environ.get('GROQ_API_KEY'), http_client=httpx.Client(proxies=""))
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": conversation}, {"role": "user", "content": speech_result or "Hello"}],
            model="llama3-8b-8192",
        )
        ai_response = chat_completion.choices[0].message.content.strip()
        conversation += f"\n\nAI: {ai_response}"
    except Exception as e:
        ai_response = "I'm sorry, I seem to be having some technical trouble right now."
        print(f"Error calling Groq: {e}")

    response = VoiceResponse()
    
    # Generate the audio and store it in our cache
    audio_data = get_elevenlabs_audio(ai_response)
    if audio_data:
        clip_id = str(uuid.uuid4())
        audio_cache[clip_id] = audio_data
        
        audio_url = f"{request.host_url}play-audio/{clip_id}"
        gather = response.gather(input='speech', action='/voice', speechTimeout='auto', enhanced="true")
        gather.play(audio_url)
    else:
        # Fallback to robotic voice if ElevenLabs fails
        gather = response.gather(input='speech', action='/voice', speechTimeout='auto')
        gather.say("My apologies, but my voice seems to be having an issue. Could you say that again?", voice='alice')

    response.redirect('/voice')

    resp = app.make_response(str(response))
    resp.set_cookie('conversation', conversation)
    resp.set_cookie('user_name', user_name)
    return resp

@app.route("/play-audio/<clip_id>")
def play_audio(clip_id):
    """Plays back the cached audio clip."""
    audio_data = audio_cache.pop(clip_id, None)
    if audio_data:
        return Response(audio_data, mimetype="audio/mpeg")
    else:
        # Return a 404 if the clip is not found
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
