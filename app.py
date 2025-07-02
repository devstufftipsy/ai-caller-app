from flask import Flask, request, Response
from groq import Groq
import os
import httpx
from urllib.parse import quote
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client

app = Flask(__name__)

SYSTEM_PROMPT_TEMPLATE = """
You are 'Alex', a friendly and professional marketing agent for 'Pixel Perfect'.
Your goal is to speak with {user_name} about a free trial of a new AI-powered photo editing software.
Keep your responses very short, natural, and conversational, like a real human on a phone call.
Never say you are an AI.
"""

def generate_audio_stream(text_to_speak):
    """A generator function that yields audio chunks from ElevenLabs."""
    ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
    VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text_to_speak,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }

    with httpx.stream("POST", url, json=data, headers=headers, timeout=20) as r:
        for chunk in r.iter_bytes(chunk_size=1024):
            yield chunk

@app.route("/voice", methods=['POST'])
def voice():
    user_name = request.cookies.get('user_name', 'the user')
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(user_name=user_name)

    speech_result = request.form.get('SpeechResult', '').strip()
    conversation = request.cookies.get('conversation', system_prompt)

    if speech_result:
        conversation += f"\n\nUser: {speech_result}"

    try:
        client = Groq(
            api_key=os.environ.get('GROQ_API_KEY'),
            http_client=httpx.Client(proxies=""),
        )
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": conversation}, {"role": "user", "content": speech_result or "Hello"}],
            model="llama3-8b-8192",
        )
        ai_response = chat_completion.choices[0].message.content.strip()
        conversation += f"\n\nAI: {ai_response}"

    except Exception as e:
        ai_response = "I'm sorry, I seem to be having some technical trouble. Could you repeat that?"
        print(f"Error calling Groq: {e}")

    response = VoiceResponse()

    # --- THIS IS THE FINAL FIX ---
    # We now nest the <Play> command inside the <Gather> command.
    gather = response.gather(input='speech', action='/voice', speechTimeout='auto', enhanced="true")
    encoded_text = quote(ai_response)
    audio_stream_url = f"{request.host_url}audio-stream?text={encoded_text}"
    gather.play(audio_stream_url)

    # Add a redirect in case the gather times out without speech
    response.redirect('/voice')

    resp = app.make_response(str(response))
    resp.set_cookie('conversation', conversation)
    resp.set_cookie('user_name', user_name)
    return resp

@app.route("/audio-stream")
def audio_stream():
    text_to_speak = request.args.get("text", "Hello there!")
    return Response(generate_audio_stream(text_to_speak), mimetype="audio/mpeg")

@app.route('/make-call/<user_name>')
def make_call(user_name):
    try:
        client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
        voice_url = f"{request.host_url}voice"

        call = client.calls.create(
            to=os.environ.get('MY_PHONE_NUMBER'),
            from_=os.environ.get('TWILIO_PHONE_NUMBER'),
            url=voice_url
        )

        resp = app.make_response(f"Success! Initiating call to {user_name}. SID: {call.sid}")
        resp.set_cookie('user_name', user_name)
        resp.set_cookie('conversation', expires=0) # Clear old conversation
        return resp

    except Exception as e:
        return f"Error making call: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
