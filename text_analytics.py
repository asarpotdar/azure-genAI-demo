import azure.cognitiveservices.speech as speechsdk
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential

# Azure Speech SDK configuration
speech_key = "BXTsAN1x0lV6qPktdlr9iM8yba6yJSWiYdx255L3QgKUtmybuXXeJQQJ99AKACYeBjFXJ3w3AAAAACOGoYyf"
service_region = "eastus"

# Azure Text Analytics configuration
text_analytics_endpoint = "https://ai-sarpotdaratul2956ai274315666685.cognitiveservices.azure.com/"
text_analytics_api_key = "BXTsAN1x0lV6qPktdlr9iM8yba6yJSWiYdx255L3QgKUtmybuXXeJQQJ99AKACYeBjFXJ3w3AAAAACOGoYyf"

# Function to authenticate Text Analytics client
def authenticate_text_analytics_client():
    credential = AzureKeyCredential(text_analytics_api_key)
    client = TextAnalyticsClient(endpoint=text_analytics_endpoint, credential=credential)
    return client

# Function to analyze text for intent
def analyze_text_sentiment(text):
    client = authenticate_text_analytics_client()
    response = client.analyze_sentiment([text])[0]
    return response.sentiment

def analyze_text_intent(text):
    client = authenticate_text_analytics_client()
    response = client.extract_key_phrases([text])[0]
    if not response.is_error:
        return response.key_phrases
    else:
        return "Error: {}".format(response.error)

# Function to recognize speech and analyze intent
def recognize_speech_and_analyze_intent():
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)

    print("Say something...")

    result = speech_recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print("Recognized: {}".format(result.text))
        intent = analyze_text_intent(result.text)
        print("Identified Intent: {}".format(intent))
    elif result.reason == speechsdk.ResultReason.NoMatch:
        print("No speech could be recognized: {}".format(result.no_match_details))
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print("Speech Recognition canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))

# Run the function
recognize_speech_and_analyze_intent()