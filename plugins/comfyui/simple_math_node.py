"""
Simple Math Node - Single File Example

This demonstrates a single-file custom node for ComfyUI.
It provides basic math operations.
"""


class SimpleMathNode:
    """
    A simple node that performs basic math operations.
    Single-file custom nodes are useful for simple functionality.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value_a": ("FLOAT", {"default": 1.0, "min": -10000, "max": 10000}),
                "operation": (
                    ["add", "subtract", "multiply", "divide"],
                    {"default": "add"},
                ),
                "value_b": ("FLOAT", {"default": 1.0, "min": -10000, "max": 10000}),
            }
        }

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "calculate"
    CATEGORY = "airpods/math"

    def calculate(self, value_a, operation, value_b):
        """Perform the selected math operation."""
        if operation == "add":
            result = value_a + value_b
        elif operation == "subtract":
            result = value_a - value_b
        elif operation == "multiply":
            result = value_a * value_b
        elif operation == "divide":
            if value_b == 0:
                raise ValueError("Cannot divide by zero")
            result = value_a / value_b
        else:
            raise ValueError(f"Unknown operation: {operation}")

        return (result,)


# Required for single-file custom nodes
NODE_CLASS_MAPPINGS = {
    "AirPodsSimpleMath": SimpleMathNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AirPodsSimpleMath": "Simple Math (AirPods)",
}
