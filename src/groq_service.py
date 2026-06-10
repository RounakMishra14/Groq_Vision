import base64

from groq import Groq

from src.config import (
    GROQ_API_KEY,
    MODEL_NAME
)


# ==========================
# Client Initialization
# ==========================

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=GROQ_API_KEY)


# ==========================
# Image Utilities
# ==========================

def encode_image_to_base64(image_path: str) -> str:
    """
    Convert image file to base64 string.
    """

    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ==========================
# Prompt Builder
# ==========================

def build_mcq_prompt(image_number: int) -> str:
    """
    Build extraction prompt for Groq Vision.
    """

    return f"""
You are an OCR and MCQ extraction assistant.

This is image number {image_number}.

STRICT RULES:
1. Extract ONLY what is visible in the image.
2. Never invent text.
3. Never solve the question yourself.
4. If text is unreadable, write [UNCLEAR].
5. Preserve question numbers exactly.
6. Preserve option labels exactly: A, B, C, D, E.
7. Return ALL visible MCQs.
8. Generate the answer ONLY if the answer is explicitly printed/visible in the image.
9. If the image does not show the answer, write exactly: Answer: Not available.
10. Do not infer the answer from your own knowledge.
11. Do not explain anything.
12. Output only structured MCQ text.

Format:

Question <number>:
<question text>

Options:
A. <option text>
B. <option text>
C. <option text>
D. <option text>

Answer: <visible answer or Not available>
"""


# ==========================
# Vision Extraction
# ==========================

def extract_mcq_with_groq(
    image_path: str,
    image_number: int
) -> str:
    """
    Extract MCQs from image using Groq Vision.
    """

    image_b64 = encode_image_to_base64(image_path)

    prompt = build_mcq_prompt(image_number)

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    }
                ]
            }
        ],
        temperature=0,
        max_completion_tokens=4096,
        top_p=1,
        stream=False,
    )

    return completion.choices[0].message.content


# ==========================
# Batch Extraction
# ==========================

def process_images(
    image_paths: list[str]
) -> list[dict]:
    """
    Process multiple images.
    Returns extraction results.
    """

    results = []

    for idx, image_path in enumerate(image_paths, start=1):

        output = extract_mcq_with_groq(
            image_path=image_path,
            image_number=idx
        )

        results.append(
            {
                "image_number": idx,
                "output": output
            }
        )

    return results