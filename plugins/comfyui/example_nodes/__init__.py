"""
Example ComfyUI Custom Node Package

This demonstrates a directory-based custom node that adds
simple text processing nodes to ComfyUI.
"""


class TextCombine:
    """
    A simple node that combines two text inputs with a separator.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text1": ("STRING", {"multiline": True, "default": "Hello"}),
                "text2": ("STRING", {"multiline": True, "default": "World"}),
                "separator": ("STRING", {"default": " "}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "combine"
    CATEGORY = "airpods/text"

    def combine(self, text1, text2, separator):
        """Combine two text strings with a separator."""
        result = f"{text1}{separator}{text2}"
        return (result,)


class TextRepeat:
    """
    A simple node that repeats text a specified number of times.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "Hello"}),
                "count": ("INT", {"default": 3, "min": 1, "max": 100}),
                "separator": ("STRING", {"default": "\n"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "repeat"
    CATEGORY = "airpods/text"

    def repeat(self, text, count, separator):
        """Repeat text a specified number of times."""
        result = separator.join([text] * count)
        return (result,)


# This dictionary is required for ComfyUI to discover your nodes
NODE_CLASS_MAPPINGS = {
    "AirPodsTextCombine": TextCombine,
    "AirPodsTextRepeat": TextRepeat,
}

# Optional: Display names for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "AirPodsTextCombine": "Text Combine (AirPods)",
    "AirPodsTextRepeat": "Text Repeat (AirPods)",
}
