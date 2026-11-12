import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=60000)
)

models = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite"
]

for model in models:
    print(f"\nTesting: {model}")
    start = time.time()

    try:
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: CampusIQ is working.",
            config=types.GenerateContentConfig(
                max_output_tokens=100
            )
        )

        print("Response:", response.text)
        print("Time:", round(time.time() - start, 2), "seconds")

    except Exception as e:
        print("Error:", type(e).__name__, str(e))