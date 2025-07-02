from flask import Flask, request, Response
from groq import Groq
import os
import httpx
from urllib.parse import quote # Import the URL encoding tool

app = Flask(__name__)

# --- The NEW, SMARTER System Prompt ---
SYSTEM_PROMPT_TEMPLATE = """
You are 'Alex', a friendly and professional marketing agent for 'Pixel Perfect'.
Your goal is to speak with {user_name} about a free trial of a new AI-powered photo editing software.
Keep your responses very short, natural, and conversational, like a real human on a phone call.
Never say you are an AI.
"""

def stream_elevenlabs_audio(text_to_speak):
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
        return Response(r.iter_bytes(chunk_size=1024), mimetype="audio/mpeg")

@app.route("/voice", methods=['POST'])
def voice():
    from twilio.twiml.voice_response import VoiceResponse

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

    # --- THIS IS THE FIX ---
    # We now safely encode the AI's response before putting it in the URL.
    encoded_text = quote(ai_response)
    audio_stream_url = f"{request.host_url}audio-stream?text={encoded_text}"

    response.play(audio_stream_url)
    response.gather(input='speech', action='/voice', speechTimeout='auto', enhanced="true")

    resp = app.make_response(str(response))
    resp.set_cookie('conversation', conversation)
    resp.set_cookie('user_name', user_name)
    return resp

@app.route("/audio-stream")
def audio_stream():
    text_to_speak = request.args.get("text", "Hello there!")
    return stream_elevenlabs_audio(text_to_speak)

@app.route('/make-call/<user_name>')
def make_call(user_name):
    from twilio.rest import Client
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
        resp.set_cookie('conversation', expires=0)
        return resp

    except Exception as e:
        return f"Error making call: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
