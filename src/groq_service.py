from __future__ import annotations

import base64
import time
from dataclasses import dataclass

from groq import Groq

from src.config import MODEL_NAME


@dataclass
class GroqExtractionResult:
    output: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    duration_seconds: float


def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_mcq_prompt(image_number: int) -> str:
    return f"""
You are an OCR and MCQ extraction assistant.

This is image number {image_number}.

Your task is to perform a COMPLETE visual transcription of every visible MCQ in the image.

STRICT RULES:
1. Extract ONLY text that is physically visible in the image.
2. Never invent, infer, complete, summarize, or rewrite text.
3. Never solve the question using your own knowledge.
4. If any text is unreadable, write exactly: [UNCLEAR]
5. Preserve question numbers exactly as shown.
6. Preserve question wording exactly as shown.
7. Preserve option labels exactly as shown.
8. Questions may contain 4, 5, or more visible options. Extract EVERY visible option label and option text.
9. Return ALL visible MCQs found in the image.
10. Carefully inspect the ENTIRE image from top to bottom before responding.
11. Do NOT stop reading after option D.
12. If option E is visible, include option E.
13. Some options may appear near the bottom edge of the image. Do not ignore text near image boundaries.
14. Some options may span multiple lines. Include the complete option text.
15. Some options may be separated by large whitespace. Continue scanning until the next question or end of visible content.
16. If part of an option is visible, extract the visible portion and mark missing text as [UNCLEAR].
17. Generate an answer ONLY if the answer is explicitly printed or visible in the image.
18. If the answer is not visible, write exactly: Answer: Not available
19. Do not infer answers from your own knowledge.
20. Do not explain anything.
21. Output ONLY structured MCQ text.

FINAL VERIFICATION CHECK:
Before generating the response:
* Scan the entire image one final time from top to bottom.
* Count all visible option labels.
* Verify every visible option label has been extracted.
* Verify no visible option has been skipped.
* Verify text near the bottom edge has been checked.
* If option E is visible, include option E.
* If additional visible options exist beyond D, include them.
* Do not stop extraction after option D.

OUTPUT FORMAT:

Question <number>: <question text>

Options:
A. <option text>
B. <option text>
C. <option text>
D. <option text>
E. <option text> (only if visible)

Answer: <visible answer or Not available>
"""


def extract_mcq_with_groq_result(
    image_path: str,
    image_number: int,
    groq_api_key: str,
    max_completion_tokens: int = 2048,
) -> GroqExtractionResult:
    if not groq_api_key:
        raise ValueError("Groq API key is missing. Please save your Groq API key after login.")

    client = Groq(api_key=groq_api_key)
    image_b64 = encode_image_to_base64(image_path)
    prompt = build_mcq_prompt(image_number)

    start_time = time.time()

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
        temperature=0,
        max_completion_tokens=max_completion_tokens,
        top_p=1,
        stream=False,
    )

    duration = time.time() - start_time
    usage = getattr(completion, "usage", None)

    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)

    return GroqExtractionResult(
        output=completion.choices[0].message.content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=MODEL_NAME,
        duration_seconds=duration,
    )


def extract_mcq_with_groq(
    image_path: str,
    image_number: int,
    groq_api_key: str,
) -> str:
    result = extract_mcq_with_groq_result(
        image_path=image_path,
        image_number=image_number,
        groq_api_key=groq_api_key,
    )
    return result.output


def process_images(
    image_paths: list[str],
    groq_api_key: str,
) -> list[dict]:
    results = []

    for idx, image_path in enumerate(image_paths, start=1):
        result = extract_mcq_with_groq_result(
            image_path=image_path,
            image_number=idx,
            groq_api_key=groq_api_key,
        )

        results.append(
            {
                "image_number": idx,
                "output": result.output,
                "usage": {
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_tokens": result.total_tokens,
                    "duration_seconds": result.duration_seconds,
                    "model": result.model,
                },
            }
        )

    return results
