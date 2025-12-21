"""ComfyUI AirPods Tools custom nodes."""

from .nodes import (
    LlamaChatCompletion,
    LlamaTextCompletion,
    OllamaChat,
    OllamaGenerate,
    TextCombine,
    TextRepeat,
)

NODE_CLASS_MAPPINGS = {
    "AirPodsLlamaTextCompletion": LlamaTextCompletion,
    "AirPodsLlamaChatCompletion": LlamaChatCompletion,
    "AirPodsOllamaGenerate": OllamaGenerate,
    "AirPodsOllamaChat": OllamaChat,
    "AirPodsTextCombine": TextCombine,
    "AirPodsTextRepeat": TextRepeat,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AirPodsLlamaTextCompletion": "Llama Text Completion (AirPods)",
    "AirPodsLlamaChatCompletion": "Llama Chat Completion (AirPods)",
    "AirPodsOllamaGenerate": "Ollama Generate (AirPods)",
    "AirPodsOllamaChat": "Ollama Chat (AirPods)",
    "AirPodsTextCombine": "Text Combine (AirPods)",
    "AirPodsTextRepeat": "Text Repeat (AirPods)",
}
