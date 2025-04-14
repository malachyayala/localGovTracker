# localNewsTracker/ai_utils.py

import os
# Use the specific `google.generativeai` library
from google import genai
from google.genai import types
from dotenv import load_dotenv
import logging
from typing import Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables


# --- Safety Settings ---
# Keep these as they are important for responsible AI use
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
]
# --- End Safety Settings ---

# Use the correct Union type hint for Python 3.9
def generate_summary(bill_text: str) -> Union[str, None]:
    """
    Generates a concise summary of the provided bill text using the Gemini API.

    Args:
        bill_text: The full text of the legislative bill.

    Returns:
        The generated summary as a string, or None if an error occurs or no text provided.
    """
    load_dotenv()
    
    # Validate API key
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    # Check if the client was successfully initialized
    if not client:
        logger.error("AI client is not configured. Cannot generate summary.")
        return None

    # Keep the basic check for empty or very short text
    if not bill_text or not isinstance(bill_text, str) or len(bill_text.strip()) < 50:
        logger.warning("Bill text is too short or invalid. Skipping summary generation.")
        return None

    # WARNING: No artificial text limit. Might exceed API limits for very long bills.

    prompt = f"""You will be provided with the following legislative bill:

    Bill Text:
    ---
    {bill_text}
    ---
    
    Summarize this bill in a way that is easy for the everyday person to understand. 
    Avoid legal jargon and technical terms. 
    Focus on explaining how this bill might impact their daily lives.  
    For example, mention any potential changes to taxes, regulations, or services.  
    If the bill involves complex legal concepts, explain them using simple analogies or examples.  
    Conclude with a brief statement summarizing the overall purpose and potential impact of the bill. 

    Summary:
    
    """

    try:
        # --- Use the configured client/model instance ---
        # Get the specific model instance from the client
        # model = genai_client.get_model("models/gemini-1.5-flash-latest") # Construct model name
        # response = model.generate_content(
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            config=types.GenerateContentConfig(
                system_instruction=f"""You are a legislative analyst tasked with explaining 
                complex bills to the public in a clear and accessible way.
                
                * keep your summaries under 600 words
                * include a bolded title with every summary
                * keep it condense and to the point
                * do not hallucinate
                """),
            contents=prompt
        )
        print(response.text)
        # --- End Client/Model Usage ---


        # Check for safety blocks or empty response
        if not response.candidates:
             block_reason = getattr(response.prompt_feedback, 'block_reason', 'Unknown')
             block_reason_message = getattr(response.prompt_feedback, 'block_reason_message', 'No details provided')
             logger.warning(f"Summary generation blocked for safety reasons: {block_reason}. Message: {block_reason_message}")
             return None

        if not response.text:
             logger.warning("Summary generation resulted in empty response text, despite candidates being present.")
             return None

        summary = response.text.strip()
        logger.info("Successfully generated summary.")
        return summary

    # Catch specific API errors if possible, otherwise generic Exception
    except Exception as e:
        if "context length" in str(e).lower() or "token limit" in str(e).lower() or "size limit" in str(e).lower():
             logger.error(f"Error during Gemini API call - potentially exceeded input limit: {e}")
        else:
             logger.error(f"Error during Gemini API call: {e}")
        return None