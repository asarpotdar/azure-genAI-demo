import azure.functions as func
import azure.cognitiveservices.speech as speechsdk
import openai
import os

# Azure Speech SDK configuration
speech_key = os.getenv("SPEECH_KEY")
service_region = os.getenv("SERVICE_REGION")

# OpenAI configuration
openai.api_key = os.getenv("OPENAI_API_KEY")

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Get the audio file from the request
        audio_file = req.files.get('audio')
        if not audio_file:
            return func.HttpResponse("Please provide an audio file.", status_code=400)

        # Recognize speech from the audio file
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        audio_input = speechsdk.AudioConfig(filename=audio_file.filename)
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input)

        result = speech_recognizer.recognize_once()
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            recognized_text = result.text
        else:
            return func.HttpResponse("Speech recognition failed.", status_code=500)

        # Call OpenAI API with the recognized text
        response = openai.Completion.create(
            engine="davinci",
            prompt=recognized_text,
            max_tokens=50
        )

        # Get the response from OpenAI
        openai_response = response.choices[0].text.strip()

        return func.HttpResponse(f"Recognized Text: {recognized_text}\nOpenAI Response: {openai_response}", status_code=200)

    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)
