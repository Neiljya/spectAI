import ollama
import base64

with open("test_frame.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

response = ollama.chat(
    model="gemma4:e2b",
    messages=[
        {"role": "user", "images": [b64], "content": "Describe what you see in this image in one sentence."}
    ]
)
print(repr(response["message"]["content"]))