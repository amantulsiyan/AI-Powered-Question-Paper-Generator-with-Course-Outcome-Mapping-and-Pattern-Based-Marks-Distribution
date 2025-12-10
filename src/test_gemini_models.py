
import os
import google.generativeai as genai

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not set")

genai.configure(api_key=api_key)

print("Available models for this API key:\n")
for m in genai.list_models():
    # Only show models that support text generation
    methods = getattr(m, "supported_generation_methods", [])
    print(m.name, "| methods:", methods)

