for agents, using WebSockets for real-time updates.
Implement a simple routing mechanism for bot-to-agent handover using Azure Web PubSub.
Enable direct communication between the mobile app and agent app post-handover.
Azure Services Used:
Azure Bot Service: Handles customer interactions and greetings.
Azure Functions: Orchestrates API requests, aggregates messages, and calls GPT-4o.
Azure AI Studio (GPT-4o): Performs dispute analysis (intent and category).
Azure Web PubSub: Manages WebSocket connections for agent updates and bot-to-agent handover.
Power Automate: Automates case creation and refund initiation.
Azure API Management: Secures API calls for refund initiation.
Azure Key Vault: Stores API keys securely.
Role of Azure Bot Service (Recap and Update)
Greeting: Responds to customer messages with a personalized greeting (e.g., “Hello! How can I help?”).
Message Capture: Captures messages from the mobile app and forwards them to the Azure Function via an HTTP API.
Handover: Initiates handover to an agent when a dispute is detected, using Web PubSub to route the conversation.
Post-Handover: Optionally relays messages between the mobile app and agent app after handover.
Integration Pattern
1. Mobile App to Azure Bot Service
The mobile app sends messages to the Azure Bot Service via a chat channel (e.g., Direct Line API).
The bot responds with a greeting and forwards messages to an Azure Function via an HTTP POST request.
2. Azure Function Orchestration
The Azure Function:
Receives messages via an HTTP API.
Aggregates messages in-memory (e.g., within a 30-second window) using a dictionary or cache.
Calls Azure AI Studio (GPT-4o) for dispute analysis.
Sends results (conversation, intent, dispute category) to the agent web app via Azure Web PubSub.
Triggers Power Automate for case creation or refund initiation.
3. Agent Web App
A simple HTML/JavaScript web app hosted on Azure App Service or Static Web Apps.
Uses Azure Web PubSub to receive real-time updates (conversation, intent, dispute category).
Displays the ongoing conversation and analysis results.
4. Bot-to-Agent Handover
When a dispute is detected (e.g., intent = “Dispute”), the Azure Function sends a handover signal via Web PubSub to an available agent’s web app.
A simple routing mechanism assigns the conversation to an agent based on availability (tracked in-memory or via Azure Redis Cache).
5. Post-Handover Communication
After handover, the mobile app communicates directly with the agent’s web app via Web PubSub, bypassing the bot for human-assisted interactions.
Sample Code
1. Azure Bot Service (Bot Framework SDK)
This code runs in Azure Bot Service, sends greetings, and forwards messages to the Azure Function.
python
from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import Activity
import requests
import json
from datetime import datetime
import pytz

class BankingBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        # Extract customer message and metadata
        customer_message = turn_context.activity.text
        session_id = turn_context.activity.conversation.id
        customer_id = turn_context.activity.from_property.id
        timestamp = datetime.now(pytz.timezone("Asia/Kolkata")).isoformat()

        # Send greeting
        if "hi" in customer_message.lower() or "hello" in customer_message.lower():
            greeting = f"Hello! I'm here to assist you with your banking needs. How can I help?"
        else:
            greeting = "Thanks for reaching out! Please provide more details about your issue."
        await turn_context.send_activity(greeting)

        # Forward message to Azure Function
        payload = {
            "session_id": session_id,
            "customer_id": customer_id,
            "message_text": customer_message,
            "timestamp": timestamp
        }
        response = requests.post(
            "https://<function-app>.azurewebsites.net/api/orchestrate",
            json=payload,
            headers={"x-functions-key": "<function-key>"}
        )
        if response.status_code == 200 and response.json().get("handover"):
            # Signal handover to agent via Web PubSub
            await self.send_handover_signal(turn_context, session_id, customer_id)

    async def send_handover_signal(self, turn_context: TurnContext, session_id: str, customer_id: str):
        # Notify customer of handover
        await turn_context.send_activity("I'm connecting you to an agent for further assistance.")
        # Send handover signal via Web PubSub (implemented in Azure Function)
Deployment: Deploy to Azure Bot Service via the Azure Portal or VS Code. Configure the Direct Line channel for mobile app integration.
Notes:
The bot sends messages to the Azure Function’s HTTP API, secured with a function key.
If the Azure Function signals a handover (e.g., dispute detected), the bot notifies the customer and triggers the handover process.
2. Azure Function (Orchestration and GPT-4o Call)
This function aggregates messages, calls GPT-4o for dispute analysis, sends results to the agent web app, and triggers automation.
python
import azure.functions as func
import requests
import json
from azure.webpubsub import WebPubSubClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from collections import defaultdict
from datetime import datetime, timedelta
import pytz

# In-memory storage for message aggregation
conversation_cache = defaultdict(list)
last_message_time = {}

def main(req: func.HttpRequest) -> func.HttpResponse:
    # Parse incoming message
    data = req.get_json()
    session_id = data["session_id"]
    customer_id = data["customer_id"]
    message_text = data["message_text"]
    timestamp = datetime.fromisoformat(data["timestamp"])

    # Aggregate messages (30-second window)
    current_time = datetime.now(pytz.timezone("Asia/Kolkata"))
    if session_id in last_message_time and (current_time - last_message_time[session_id]).total_seconds() > 30:
        conversation_cache[session_id].clear()  # Clear old messages
    conversation_cache[session_id].append(message_text)
    last_message_time[session_id] = current_time

    # Call GPT-4o for dispute analysis
    conversation = conversation_cache[session_id]
    prompt = f"""
    Given the following customer conversation, classify the intent as "Dispute", "AccountInquiry", or "Other". If the intent is "Dispute", categorize it as "UnauthorizedTransaction", "BillingIssue", or "OtherDispute". Provide the output in JSON format.
    Conversation: {conversation}
    Output format: {{"intent": "<intent>", "dispute_category": "<category or null>"}}
    """
    
    gpt_endpoint = "https://<endpoint>.azure.com/score"
    headers = {
        "Authorization": f"Bearer {get_key_from_vault()}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": prompt,
        "max_tokens": 100,
        "temperature": 0.3
    }
    response = requests.post(gpt_endpoint, json=payload, headers=headers)
    result = json.loads(response.json()["choices"][0]["text"])
    
    # Prepare output
    output = {
        "session_id": session_id,
        "customer_id": customer_id,
        "conversation": conversation,
        "intent": result["intent"],
        "dispute_category": result["dispute_category"],
        "handover": result["intent"] == "Dispute"  # Trigger handover for disputes
    }
    
    # Send to agent web app via Web PubSub
    send_to_webpubsub(output)
    
    # Trigger automation for disputes
    if output["handover"]:
        trigger_automation(output)
    
    return func.HttpResponse(json.dumps(output), status_code=200)

def get_key_from_vault():
    vault_url = "https://<vault-name>.vault.azure.net"
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    return client.get_secret("gpt-api-key").value

def send_to_webpubsub(data):
    client = WebPubSubClient(
        connection_string="Endpoint=https://<webpubsub>.webpubsub.azure.com;AccessKey=<key>;Version=1.0;",
        hub="agent-updates"
    )
    # Route to available agent
    agent_id = get_available_agent(data["session_id"])
    client.send_to_group(f"agent-{agent_id}", json.dumps(data), "json")

def get_available_agent(session_id):
    # Simple routing: Use Redis or in-memory list for agent availability
    # For simplicity, assume a static agent ID
    return "agent-001"  # Replace with logic to select available agent

def trigger_automation(data):
    # Trigger Power Automate via HTTP POST (e.g., for case creation or refund)
    power_automate_url = "https://<flow>.flow.microsoft.com/trigger"
    requests.post(power_automate_url, json=data)
Notes:
The function uses an in-memory defaultdict to aggregate messages within a 30-second window, clearing old messages to mimic the tumbling window behavior without storage.
GPT-4o is called for dispute analysis, with results sent to Web PubSub for agent display.
If intent = “Dispute”, the handover flag is set to trigger bot-to-agent handover.
Deployment: Deploy as an HTTP-triggered Azure Function.
3. Agent Web App (HTML/JavaScript with WebSocket)
This is a simple web app hosted on Azure App Service or Static Web Apps, displaying conversation and analysis results.
html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Agent Web App</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #conversation, #intent, #dispute_category { margin: 10px 0; }
        #chat-input { width: 100%; padding: 10px; }
        #chat-messages { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: scroll; }
    </style>
</head>
<body>
    <h2>Agent Web App</h2>
    <div>
        <strong>Conversation:</strong>
        <div id="conversation"></div>
    </div>
    <div>
        <strong>Intent:</strong>
        <div id="intent"></div>
    </div>
    <div>
        <strong>Dispute Category:</strong>
        <div id="dispute_category"></div>
    </div>
    <div>
        <strong>Chat with Customer:</strong>
        <div id="chat-messages"></div>
        <input type="text" id="chat-input" placeholder="Type your message...">
        <button onclick="sendMessage()">Send</button>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/@azure/web-pubsub-client@1.0.0/dist/web-pubsub-client.min.js"></script>
    <script>
        const agentId = "agent-001"; // Replace with dynamic agent ID
        const client = new WebPubSubClient({
            connectionString: "Endpoint=https://<webpubsub>.webpubsub.azure.com;AccessKey=<key>;Version=1.0;",
            hub: "agent-updates"
        });

        client.start();
        client.joinGroup(`agent-${agentId}`);

        // Handle incoming conversation and analysis
        client.on("message", (message) => {
            const data = JSON.parse(message.data);
            document.getElementById("conversation").innerText = data.conversation.join("\n");
            document.getElementById("intent").innerText = data.intent;
            document.getElementById("dispute_category").innerText = data.dispute_category || "N/A";
            if (data.handover) {
                document.getElementById("chat-messages").innerText += `System: Handover for session ${data.session_id}\n`;
            }
        });

        // Send messages to customer (post-handover)
        function sendMessage() {
            const message = document.getElementById("chat-input").value;
            const sessionId = getSessionId(); // Retrieve from context or WebSocket message
            client.sendToGroup(`customer-${sessionId}`, JSON.stringify({
                from: agentId,
                message: message
            }), "json");
            document.getElementById("chat-messages").innerText += `Agent: ${message}\n`;
            document.getElementById("chat-input").value = "";
        }

        function getSessionId() {
            // Extract from WebSocket message or UI context
            return document.getElementById("conversation").dataset.sessionId || "S789";
        }
    </script>
</body>
</html>
Deployment: Host on Azure Static Web Apps or App Service. Configure Web PubSub connection string in the JavaScript.
Notes:
The web app displays the conversation, intent, and dispute category received via Web PubSub.
Post-handover, agents can send messages to the customer’s mobile app via Web PubSub groups (customer-<session_id>).
Security: Secure WebSocket connections with access tokens or Azure AD.
4. Mobile App (Post-Handover Communication)
The mobile app integrates with Azure Web PubSub for direct communication with the agent after handover.
javascript
// Example JavaScript for mobile app (e.g., React Native)
import { WebPubSubClient } from "@azure/web-pubsub-client";

const client = new WebPubSubClient({
    connectionString: "Endpoint=https://<webpubsub>.webpubsub.azure.com;AccessKey=<key>;Version=1.0;",
    hub: "agent-updates"
});

client.start();
client.joinGroup(`customer-<session_id>`);

// Handle messages from agent
client.on("message", (message) => {
    const data = JSON.parse(message.data);
    console.log(`Agent: ${data.message}`);
    // Update mobile app UI with agent's message
});

// Send message to agent
function sendToAgent(message) {
    client.sendToGroup(`agent-<agent_id>`, JSON.stringify({
        from: "<customer_id>",
        message: message
    }), "json");
}
Notes:
The mobile app joins a Web PubSub group (customer-<session_id>) after handover.
Messages are exchanged between customer-<session_id> and agent-<agent_id> groups.
5. Bot-to-Agent Handover (Routing Mechanism)
Mechanism:
When the Azure Function detects intent = “Dispute”, it sets handover: true in the output.
The function selects an available agent using a simple routing logic (e.g., round-robin or availability-based).
Example routing logic (in get_available_agent):
python
def get_available_agent(session_id):
    # Mock agent availability (replace with Azure Redis Cache or database)
    available_agents = ["agent-001", "agent-002", "agent-003"]
    # Simple round-robin based on session_id hash
    index = hash(session_id) % len(available_agents)
    return available_agents[index]
The Azure Function sends the conversation and analysis to the selected agent’s Web PubSub group (agent-<agent_id>).
The bot notifies the customer: “I’m connecting you to an agent.”
Post-Handover:
The mobile app and agent app communicate directly via Web PubSub groups (customer-<session_id> and agent-<agent_id>).
The bot steps back, but can relay messages if needed (e.g., via Direct Line API).
6. Automation (Power Automate)
Case Creation:
Trigger: HTTP POST from Azure Function to Power Automate (trigger_automation).
Action: Create a case in a CRM system (e.g., a lightweight database or external CRM via API):
python
import requests

def create_case(session_id, customer_id, dispute_category, conversation):
    crm_endpoint = "https://<apim-service>.azure-api.net/crm/cases"
    headers = {
        "Ocp-Apim-Subscription-Key": "<apim-key>",
        "Content-Type": "application/json"
    }
    payload = {
        "session_id": session_id,
        "customer_id": customer_id,
        "description": f"Category: {dispute_category}\nConversation: {' '.join(conversation)}",
        "priority": dispute_category == "UnauthorizedTransaction" and 1 or 2
    }
    response = requests.post(crm_endpoint, json=payload, headers=headers)
    return response.json()["case_id"]
Refund Initiation:
Trigger: dispute_category = “BillingIssue”.
Action: Call a refund API via Azure API Management:
python
import requests

def initiate_refund(transaction_id, amount, customer_id):
    apim_endpoint = "https://<apim-service>.azure-api.net/refund"
    headers = {
        "Ocp-Apim-Subscription-Key": "<apim-key>",
        "Content-Type": "application/json"
    }
    payload = {
        "transaction_id": transaction_id,
        "amount": amount,
        "customer_id": customer_id
    }
    response = requests.post(apim_endpoint, json=payload, headers=headers)
    return response.json()["refund_id"]
Sample Workflow (9:42 PM IST, June 01, 2025)
Customer Interaction:
Mobile app sends: “Hi, I was charged $50 at StoreX.” → Bot responds: “Hello! I’m here to assist you with your banking needs. How can I help?”
Customer sends: “It was yesterday, and I only made one purchase.”
Bot Service forwards messages to Azure Function via HTTP API.
Orchestration:
Azure Function aggregates messages in-memory (30-second window).
Calls GPT-4o, outputs:
json
{
  "session_id": "S789",
  "customer_id": "C12345",
  "conversation": ["I was charged $50 at StoreX", "It was yesterday, and I only made one purchase"],
  "intent": "Dispute",
  "dispute_category": "BillingIssue",
  "handover": true
}
Handover:
Bot sends: “I’m connecting you to an agent for further assistance.”
Azure Function routes to agent-001 via Web PubSub.
Agent Display:
Agent web app shows:
Conversation: “I was charged $50 at StoreX. It was yesterday, and I only made one purchase.”
Intent: “Dispute”
Category: “BillingIssue”
Post-Handover:
Customer sends: “Can you refund it?” via mobile app to customer-S789.
Agent receives message in agent-001 group and responds: “I’ll initiate the refund.”
Automation:
Power Automate creates a case and initiates a refund, notifying the customer: “Your refund for $50 is being processed.”
Additional Considerations
Security: Secure API calls with Azure API Management and WebSocket connections with Azure AD tokens. Store keys in Azure Key Vault.
Scalability: Use Azure Redis Cache for agent availability in high-volume scenarios. Scale Web PubSub for thousands of connections.
Error Handling: Implement retry logic in Azure Functions and log errors in Azure Monitor.
Compliance: Ensure GDPR/PCI DSS compliance by encrypting data and auditing interactions.
Cost: Optimize with serverless Azure Functions and monitor usage via Azure Cost Management.
This solution provides a lightweight, API-driven orchestration with a simple agent web app and WebSocket-based handover, enabling efficient dispute handling and direct mobile-agent communication. For pricing, visit Microsoft Azure. For API details, see xAI API.
