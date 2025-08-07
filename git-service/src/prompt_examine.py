import openai
from dotenv import load_dotenv
import os
from pydantic import BaseModel, Field
from typing import List

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def analyze_prompt(user_prompt: str) -> str:
    """Examine each diff and assign  to features"""
    SYSTEM_PROMPT = """You are a helpful assistant that analyzes user prompts and divides them into features.

The user will provide a prompt that can contain multiple features.

You will return a JSON object with each feature you identify.
    """


    class Feature(BaseModel):
        feature: str = Field(description="A short description of the feature")
    
    class Response(BaseModel):
        features: List[Feature]

    response = client.beta.chat.completions.parse(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"User Prompt: {user_prompt}"}
        ],
        response_format=Response
    )

    return response.choices[0].message.parsed


if __name__ == "__main__":
    user_prompt = "I want to create a Flask app and add some text files describing the coding guidelines."
    response = analyze_prompt(user_prompt)
    print(response)