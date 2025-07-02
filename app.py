from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse
from groq import Groq
import os

app = Flask(__name__)

# --- The System Prompt that defines the AI's personality and goal ---
SYSTEM_PROMPT = """
You are a friendly and professional marketing agent for a company called 'Pixel Perfect'.
Your goal is to see if the user is interested in a free trial of your new AI-powered photo editing software.
Keep your responses short, natural, and conversational.
Start the conversation by introducing yourself and asking to speak with the user by name.
"""

@app.route("/voice", methods=['POST'])
def voice():
    """This function handles the back-and-forth conversation."""
    response = VoiceResponse()

    # Get the user's spoken response from the previous turn
    speech_result = request.form.get('SpeechResult', '').strip()

    # Retrieve conversation history from the session cookie
    conversation = request.cookies.get('conversation', SYSTEM_PROMPT)

    # Add the user's response to the history
    if speech_result:
        conversation += f"\n\nUser: {speech_result}"

    try:
        # Call the Groq LLM to get the next thing to say
        client = Groq(api_key=os.environ.get('GROQ_API_KEY'))
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": conversation}, {"role": "user", "content": speech_result or "Hello"}],
            model="llama3-8b-8192",
        )
        ai_response = chat_completion.choices[0].message.content.strip()

        # Add AI response to history
        conversation += f"\n\nAI: {ai_response}"

    except Exception as e:
        ai_response = "I'm sorry, I seem to be having some technical trouble. Could you repeat that?"
        print(f"Error calling Groq: {e}")

    # Use <Gather> to speak the AI's response and then immediately listen for the user's next turn.
    gather = response.gather(input='speech', action='/voice', speechTimeout='auto', enhanced="true")
    gather.say(ai_response, voice='alice')

    # Set the updated conversation history in the cookie
    resp = app.make_response(str(response))
    resp.set_cookie('conversation', conversation)
    return resp

# This is still the "Go" button to start the call.
@app.route('/make-call')
def make_call():
    from twilio.rest import Client
    try:
        client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
        voice_url = f"https://{request.host}/voice" # Dynamically get the base URL

        call = client.calls.create(
                                to=os.environ.get('MY_PHONE_NUMBER'),
                                from_=os.environ.get('TWILIO_PHONE_NUMBER'),
                                url=voice_url
                            )
        return f"Success! Initiating conversational call. SID: {call.sid}"
    except Exception as e:
        return f"Error making call: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
