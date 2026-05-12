import os
from openai import OpenAI

class AIGenerator:
    def __init__(self):
        self.client = None
        self.model = "inclusionai/ring-2.6-1t:free"
        
        # Initialize OpenRouter client
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if api_key:
            try:
                # OpenRouter uses OpenAI-compatible API
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key
                )
                print("OpenRouter initialized successfully")
            except Exception as e:
                print(f"OpenRouter setup failed: {e}")
        else:
            print("OPENROUTER_API_KEY not set")

    def is_available(self) -> bool:
        return self.client is not None

    def generate_email(self, description: str, language: str = "arabic") -> dict:
        """
        Generate an email based on user description using OpenRouter
        Returns: {"subject": str, "body": str} or {"error": str}
        """
        if not self.is_available():
            return {"error": "OpenRouter API not configured. Set OPENROUTER_API_KEY in .env file."}

        lang_instruction = "in Arabic" if language == "arabic" else "in English"
        
        messages = [
            {
                "role": "system",
                "content": "You are a professional email writing assistant. Write professional emails with clear subject lines and well-structured bodies. Always format your response with SUBJECT: followed by the subject, then BODY: followed by the email content."
            },
            {
                "role": "user",
                "content": f"Write a professional email {lang_instruction} based on this description:\n\n{description}\n\nFormat:\nSUBJECT: [subject line]\n\nBODY:\n[email body]"
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            content = response.choices[0].message.content.strip()
            
            # Parse the response
            lines = content.split('\n')
            subject = ""
            body_lines = []
            in_body = False
            
            for line in lines:
                if line.startswith("SUBJECT:"):
                    subject = line.replace("SUBJECT:", "").strip()
                elif line.startswith("BODY:"):
                    in_body = True
                elif in_body:
                    body_lines.append(line)
            
            body = '\n'.join(body_lines).strip()
            
            if not subject or not body:
                # Fallback: try to extract subject from first line if format is wrong
                if lines:
                    subject = lines[0][:100]  # First line as subject, max 100 chars
                    body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else content
            
            return {
                "subject": subject,
                "body": body
            }
            
        except Exception as e:
            return {"error": f"Failed to generate email: {str(e)[:200]}"}
