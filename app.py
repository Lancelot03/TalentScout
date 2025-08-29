import streamlit as st
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import re
import time
import PyPDF2 ### UPGRADE ###: Import library for PDF reading

# --- Configuration ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_MODEL_NAME = os.getenv("GOOGLE_MODEL_NAME", "gemini-1.5-flash")

if not GOOGLE_API_KEY:
    st.error("Google API key not found. Please set it in your .env file.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(GOOGLE_MODEL_NAME)

# --- Streamlit UI Setup ---
CHATBOT_NAME = "TalentScout Assistant"
st.set_page_config(page_title=CHATBOT_NAME, layout="centered")
st.title(f"👋 Welcome to the {CHATBOT_NAME}!")
st.subheader("Your AI-powered Hiring Assistant for Tech Placements")

# --- Python-Managed State and Flow ---
FIELD_CONFIG = {
    "full_name": "To start, what is your full name?",
    "email": "Thank you. What is your email address?",
    "phone_number": "Got it. And what is your phone number?",
    "years_experience": "Thanks. Which of these best describes your professional experience level? (e.g., 'Junior: 0-2 years', 'Mid-level: 2-5 years', 'Senior: 5+ years')",
    "desired_positions": "What position(s) are you looking for (e.g., AI Engineer, Frontend Developer)?",
    "current_location": "And where are you currently located (City, Country)?",
    "tech_stack": "Finally, please list your primary tech stack (e.g., Python, React, AWS)."
}

# --- Initialize Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "candidate_info" not in st.session_state:
    st.session_state.candidate_info = {key: None for key in FIELD_CONFIG}
if "current_field" not in st.session_state:
    st.session_state.current_field = "full_name"
### UPGRADE ###: New 'upload' stage at the beginning.
if "stage" not in st.session_state:
    st.session_state.stage = "upload_resume"

# --- Core Functions ---

### UPGRADE ###: New functions for PDF processing and pre-filling.
def extract_text_from_pdf(pdf_file):
    """Extracts text from an uploaded PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
        return text
    except Exception as e:
        st.error(f"Error reading PDF file: {e}")
        return None

def prefill_info_with_llm(resume_text):
    """Uses the LLM to parse resume text and pre-fill candidate info."""
    prompt = f"""
    You are an expert resume parser for a tech recruitment agency.
    From the following resume text, extract the candidate's information into a valid JSON object.
    The keys you must look for are: "full_name", "email", "phone_number", "current_location", and "tech_stack".
    For "tech_stack", provide a list of relevant technologies found.
    If you cannot find a specific piece of information, set its value to null.

    Resume Text:
    ---
    {resume_text}
    ---
    """
    try:
        response = model.generate_content(prompt)
        json_str = response.text.strip().replace("```json", "").replace("```", "").strip()
        print(f"--- DEBUG: Raw Resume Extraction: {json_str} ---")
        return json.loads(json_str)
    except (Exception, json.JSONDecodeError) as e:
        print(f"--- DEBUG: Resume Extraction failed: {e} ---")
        return {}


def display_chat_history():
    """Displays all messages from session state."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

def extract_info_with_llm(user_input, fields_to_extract):
    """Uses the LLM for information extraction during conversation."""
    prompt = f"""
    From the user's text, extract the following pieces of information if they exist: {', '.join(fields_to_extract)}.
    The user is currently being asked for the '{st.session_state.current_field}'. They may also provide other information.
    Return ONLY a valid JSON object with the keys you found. If you find nothing, return an empty JSON object.

    USER'S TEXT: "{user_input}"
    """
    try:
        response = model.generate_content(prompt)
        json_str = response.text.strip().replace("```json", "").replace("```", "").strip()
        print(f"--- DEBUG: Raw LLM Extraction: {json_str} ---")
        return json.loads(json_str)
    except (Exception, json.JSONDecodeError) as e:
        print(f"--- DEBUG: LLM Extraction failed or returned invalid JSON. Returning empty dict. Error: {e} ---")
        return {}

def find_next_question():
    """Python logic to find the next missing piece of information and ask the question."""
    for field, question in FIELD_CONFIG.items():
        if st.session_state.candidate_info.get(field) is None:
            st.session_state.current_field = field
            st.session_state.messages.append({"role": "assistant", "content": question})
            return True
    return False

def validate_input(field, value):
    """Checks if the input value for a given field is valid."""
    if value is None: return False, "Input cannot be empty."
    value_str = str(value).strip()
    if field == 'email':
        if not re.match(r"[^@]+@[^@]+\.[^@]+", value_str):
            return False, "That doesn't look like a valid email address. Please try again."
    elif field == 'phone_number':
        if not re.search(r"\d{7,}", value_str):
            return False, "That doesn't look like a valid phone number. Please enter a number with at least 7 digits."
    elif field == 'years_experience':
        if not any(level in value_str.lower() for level in ['junior', 'mid', 'senior', 'years']):
            return False, "Please describe your experience level (e.g., 'Junior', '5 years', 'Senior')."
    return True, ""

def generate_candidate_summary(candidate_data):
    """Uses the LLM to create a concise summary for a recruiter."""
    profile_list = [f"- {key.replace('_', ' ').title()}: {value}" for key, value in candidate_data.items()]
    profile_str = "\n".join(profile_list)
    prompt = f"""
    You are an AI specialized in writing concise candidate summaries for recruiters.
    Based on the following profile, write a concise 3-4 sentence summary.
    Highlight the experience level, key skills, and desired role.

    Candidate Profile:
    {profile_str}

    Summary:
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"--- DEBUG: Summary generation failed: {e} ---")
        return "The summary generation service failed due to a potential API connection or quota issue."

# --- Main Application Logic ---

### UPGRADE ###: New initial stage for handling resume upload.
if st.session_state.stage == "upload_resume":
    st.info("To speed things up, you can upload your resume (PDF) to pre-fill your information.")
    
    uploaded_file = st.file_uploader(
        "Upload your Resume", type=["pdf"], label_visibility="collapsed"
    )

    if st.button("Or, fill out manually", key="manual_fill"):
        st.session_state.stage = "gathering_info"
        st.session_state.messages.append({"role": "assistant", "content": FIELD_CONFIG["full_name"]})
        st.rerun()

    if uploaded_file is not None:
        with st.spinner("Analyzing resume... This may take a moment."):
            resume_text = extract_text_from_pdf(uploaded_file)
            if resume_text:
                prefilled_data = prefill_info_with_llm(resume_text)
                if prefilled_data:
                    # Intelligently merge the pre-filled data
                    for key, value in prefilled_data.items():
                        if key in st.session_state.candidate_info and value is not None:
                            st.session_state.candidate_info[key] = value
                
                st.session_state.messages.append({"role": "assistant", "content": "I've pre-filled your information from the resume. Please review it in the sidebar. I'll now ask for any missing details."})
        
        st.session_state.stage = "gathering_info"
        find_next_question() # Kick off the regular question flow
        st.rerun()

else:
    # This block runs for all other stages of the conversation
    display_chat_history()

    user_input = st.chat_input("Type your message here...")

    if user_input:
        if st.session_state.stage == 'gathering_info':
            current_field_before_update = st.session_state.current_field
            st.session_state.messages.append({"role": "user", "content": user_input})

            extracted_data = extract_info_with_llm(user_input, list(FIELD_CONFIG.keys()))
            if extracted_data and isinstance(extracted_data, dict):
                for key, value in extracted_data.items():
                    if key in st.session_state.candidate_info:
                        st.session_state.candidate_info[key] = value

            if st.session_state.candidate_info[current_field_before_update] is None:
                st.session_state.candidate_info[current_field_before_update] = user_input

            is_valid, error_message = validate_input(
                current_field_before_update,
                st.session_state.candidate_info[current_field_before_update]
            )

            if not is_valid:
                st.session_state.candidate_info[current_field_before_update] = None
                st.session_state.messages.append({"role": "assistant", "content": error_message})
            else:
                if not find_next_question():
                    st.session_state.stage = "confirming_info"
                    confirmation_text = "Great, I have all your details. Please review them carefully:\n\n"
                    for key, value in st.session_state.candidate_info.items():
                        display_key = key.replace('_', ' ').title()
                        confirmation_text += f"- **{display_key}:** {value}\n"
                    confirmation_text += "\nIs all this information correct? (yes/no)"
                    st.session_state.messages.append({"role": "assistant", "content": confirmation_text})
            st.rerun()

        elif st.session_state.stage == 'confirming_info':
            st.session_state.messages.append({"role": "user", "content": user_input})
            if 'yes' in user_input.lower().strip():
                st.session_state.stage = "generate_questions"
                st.session_state.messages.append({"role": "assistant", "content": "Excellent! Please give me a moment while I generate some technical questions."})
            else:
                st.session_state.stage = "awaiting_field_to_edit"
                st.session_state.messages.append({"role": "assistant", "content": "No problem. Which field would you like to correct?"})
            st.rerun()
        
        elif st.session_state.stage == 'awaiting_field_to_edit':
            st.session_state.messages.append({"role": "user", "content": user_input})
            field_to_edit = user_input.lower().strip().replace(' ', '_')
            if field_to_edit in FIELD_CONFIG:
                st.session_state.candidate_info[field_to_edit] = None
                st.session_state.stage = "gathering_info"
                find_next_question()
            else:
                st.session_state.messages.append({"role": "assistant", "content": "I'm sorry, I don't recognize that field. Please choose from: " + ", ".join(FIELD_CONFIG.keys())})
            st.rerun()

    if st.session_state.stage == "generate_questions":
        with st.chat_message("assistant"):
            with st.spinner("Generating technical questions..."):
                tech_stack = st.session_state.candidate_info.get("tech_stack", "general software")
                experience_level = st.session_state.candidate_info.get('years_experience', 'Mid-level')
                prompt = f"Generate 5 technical interview questions for a candidate with '{experience_level}' experience and the following tech stack: {tech_stack}. The questions should be appropriate for this experience level."
                
                questions = model.generate_content(prompt).text
                st.session_state.messages.append({"role": "assistant", "content": questions})
                
                final_message = "Here are your questions. This initial screening is now complete. Thank you for your time!"
                st.session_state.messages.append({"role": "assistant", "content": final_message})
                time.sleep(1.5)
                st.session_state.stage = "finished"
                st.rerun()

    # --- Sidebar and Progress Bar ---
    st.sidebar.subheader("Candidate Information")
    st.sidebar.json(st.session_state.candidate_info)

    if st.session_state.stage == "finished" and "summary" not in st.session_state:
        with st.sidebar:
            with st.spinner("Generating recruiter summary..."):
                summary = generate_candidate_summary(st.session_state.candidate_info)
                st.session_state.summary = summary

    if "summary" in st.session_state:
        st.sidebar.subheader("Recruiter Summary")
        st.sidebar.success(st.session_state.summary)

    if st.session_state.stage in ['gathering_info', 'confirming_info', 'awaiting_field_to_edit']:
        filled_fields = sum(1 for value in st.session_state.candidate_info.values() if value is not None)
        total_fields = len(FIELD_CONFIG)
        progress_percentage = filled_fields / total_fields
        st.progress(progress_percentage, text=f"Screening Progress: Step {filled_fields} of {total_fields}")

    if st.sidebar.button("Start New Conversation"):
        st.session_state.clear()
        st.rerun()