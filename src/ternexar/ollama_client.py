import requests
from typing import Dict, Any, Optional

class OllamaError(Exception):
    """Custom exception for Ollama-related failures."""
    def __init__(self, message: str, fix_command: Optional[str] = None):
        self.message = message
        self.fix_command = fix_command
        super().__init__(self.message)

class OllamaClient:
    """Handles raw communication with the local Ollama API."""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def generate(self, model: str, prompt: str, options: Dict[str, Any]) -> str:
        """Sends a generation request to Ollama and returns the text response."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options
        }
        
        try:
            # Using a generous timeout for local inference
            response = requests.post(url, json=payload, timeout=120)
            
            if response.status_code == 404:
                raise OllamaError(
                    f"Model '{model}' not found in local Ollama library.",
                    fix_command=f"ollama pull {model}"
                )
            
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
            
        except requests.exceptions.ConnectionError:
            raise OllamaError(
                "Could not connect to Ollama service. Is it running?",
                fix_command="ollama serve"
            )
        except requests.exceptions.Timeout:
            raise OllamaError("The request to Ollama timed out. The model might be too large for your hardware.")
        except requests.exceptions.RequestException as e:
            raise OllamaError(f"An unexpected API error occurred: {str(e)}")

ollama_client = OllamaClient()
