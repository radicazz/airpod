"""ComfyUI AirPods Tools custom nodes."""

from .nodes import (
    LlamaChatCompletion,
    LlamaTextCompletion,
    OllamaChat,
    OllamaGenerate,
)

NODE_CLASS_MAPPINGS = {
    "AirPodsLlamaTextCompletion": LlamaTextCompletion,
    "AirPodsLlamaChatCompletion": LlamaChatCompletion,
    "AirPodsOllamaGenerate": OllamaGenerate,
    "AirPodsOllamaChat": OllamaChat,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AirPodsLlamaTextCompletion": "Llama Text Completion (AirPods)",
    "AirPodsLlamaChatCompletion": "Llama Chat Completion (AirPods)",
    "AirPodsOllamaGenerate": "Ollama Generate (AirPods)",
    "AirPodsOllamaChat": "Ollama Chat (AirPods)",
}
