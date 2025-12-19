import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

candidates = [
    "gemini-2.5-flash", 
    "gemini-2.0-flash", 
    "gemini-2.0-flash-exp", 
    "gemini-2.0-flash-lite-001",
    "gemini-3-flash-preview"
]

print("Starting sequential model test...")

for model_name in candidates:
    print(f"\n--- Testing {model_name} ---")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Hello, this is a test.")
        print(f"SUCCESS! {model_name} is working.")
        print(f"Response: {response.text}")
        # break  # Stop after finding the first working model
    except Exception as e:
        # print(f"FAILED {model_name}: {e}")
        print(f"FAILED {model_name} (Error suppressed)")
    time.sleep(1) # safety delay
