import os
from phi.agent import Agent
from phi.model.groq import Groq
from phi.tools.googlesearch import GoogleSearch
from dotenv import load_dotenv
import fitz  # PyMuPDF for reading PDF files
import json  # To store and retrieve conversation history

# Load environment variables
load_dotenv()

# Function to load user conversation history
def load_user_conversation_history(user_id, conversation_history_dir="conversation_histories"):
    user_history_path = os.path.join(conversation_history_dir, f"{user_id}_history.json")
    if os.path.exists(user_history_path):
        with open(user_history_path, "r") as file:
            return json.load(file)
    return []

# Function to save user conversation history
def save_user_conversation_history(user_id, history, conversation_history_dir="conversation_histories"):
    os.makedirs(conversation_history_dir, exist_ok=True)
    user_history_path = os.path.join(conversation_history_dir, f"{user_id}_history.json")
    with open(user_history_path, "w") as file:
        json.dump(history, file, indent=4)

# Initialize the UniAssist Agent
agent = Agent(
    name="Admission Assistant",
    role="Provide accurate and detailed responses for DIU-related queries.",
    model=Groq(id="llama-3.3-70b-versatile"),
    tools=[
        GoogleSearch(),
    ],
    description=(
        "A virtual assistant specializing in academic support for Daffodil International University. "
        "It provides information on policies, courses, events, and general guidance."
    ),
    instructions=[
        "Respond concisely and accurately to user queries.",
        "If the user does not ask for specific information, act like a chatbot and engage in casual conversation.",
        "If additional resources are required, suggest them or search for the information using available tools.",
        "Structure responses clearly, using bullet points or paragraphs where necessary.",
    ],
    add_history_to_messages=True,
    show_tool_calls=True,
    markdown=True,
)

# Function to extract text from a PDF
def extract_text_from_pdf(pdf_path):
    try:
        pdf_document = fitz.open(pdf_path)
        pdf_text = ""
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            pdf_text += page.get_text()
        pdf_document.close()
        return pdf_text
    except Exception as e:
        print(f"Error reading PDF: {e}")  # Replaced st.error with print for better compatibility
        return ""

# Function to handle queries
def generate_combined_response(pdf_data, user_input, history):
    # Format the history into a single string
    formatted_history = "\n".join(
        [f"{chat['role'].capitalize()}: {chat['message']}" for chat in history]
    )
    # Format the past data into a single string
    # formatted_past_data = "\n".join(
    #     [f"{chat['role'].capitalize()}: {chat['message']}" for chat in conversation]
    # )

    # Construct the prompt to process and summarize the data
    prompt = (
        f"You are a knowledgeable assistant specializing in topics related to Daffodil International University (DIU). "
        f"Your role is to provide accurate, concise, and context-specific responses based on the following inputs:\n\n"
        f"1. **DIU Reference Document**:\n"
        f"The following document contains detailed and official information about DIU, such as policies, courses, events, and guidelines. "
        f"Use this as a key source for your response:\n{pdf_data}\n\n"
        f"2. **Important Past Data**:\n"
        f"Insights and discussions from previous seasons are critical for providing contextually relevant information. "
        # f"Here is the relevant data:\n{formatted_past_data}\n\n"
        f"3. **Conversation History**:\n"
        f"Below is the conversation history, which provides additional context about the user's current query and previous discussions:\n{formatted_history}\n\n"
        f"4. **User Query**:\n"
        f"The user has asked the following question or provided this input:\n{user_input}\n\n"
    )
    # Generate and return the response from the UniAssist agent
    response = agent.run(prompt)
    return response.content