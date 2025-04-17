from open_webui.utils.task import prompt_template, prompt_variables_template
from open_webui.utils.misc import (
    add_or_update_system_message,
)

import logging
from typing import Callable, Optional, Literal
import json

log = logging.getLogger(__name__)


# inplace function: form_data is modified
def apply_model_system_prompt_to_body(
    params: dict,
    form_data: dict,
    metadata: Optional[dict] = None,
    user=None,
    target_backend: Literal["openai", "ollama"] = "openai"
) -> dict:
    system_prompt_content = params.get("system", None)
    custom_roles = params.get("custom_roles", [])

    raw_template_vars = {}
    if metadata:
        raw_template_vars.update(metadata.get("variables", {}))

    if user:
        raw_template_vars["user_name"] = getattr(user, 'name', None)
        user_info = getattr(user, 'info', {})
        raw_template_vars["user_location"] = user_info.get("location") if isinstance(user_info, dict) else None

    template_vars = {
        k: (str(v) if v is not None and not isinstance(v, str) else v if isinstance(v, str) else "")
        for k, v in raw_template_vars.items()
    }


    formatted_system_prompt = None
    if system_prompt_content:
        try:
            sys_content_str = system_prompt_content if isinstance(system_prompt_content, str) else ""
            content_with_vars = prompt_variables_template(sys_content_str, template_vars)
            # *** FIX: Call prompt_template with only expected keyword args ***
            formatted_system_prompt = prompt_template(
                content_with_vars,
                user_name=template_vars.get("user_name"),
                user_location=template_vars.get("user_location")
            )
        except Exception as e:
            log.error(f"Error formatting system prompt: {e}")
            formatted_system_prompt = system_prompt_content if isinstance(system_prompt_content, str) else ""

    processed_custom_roles = []
    if isinstance(custom_roles, list):
        for role_def in custom_roles:
            if isinstance(role_def, dict) and "role" in role_def and "value" in role_def:
                role_name = role_def["role"]
                role_value = role_def["value"]

                role_value_str = role_value if isinstance(role_value, str) else ""

                try:
                    content_with_vars = prompt_variables_template(role_value_str, template_vars)
                    # *** FIX: Call prompt_template with only expected keyword args ***
                    formatted_content = prompt_template(
                         content_with_vars,
                         user_name=template_vars.get("user_name"),
                         user_location=template_vars.get("user_location")
                    )
                    processed_custom_roles.append({
                        "name": role_name,
                        "formatted_content": formatted_content
                    })
                except Exception as e:
                     log.error(f"Error formatting custom role '{role_name}': {e}")
                     processed_custom_roles.append({
                         "name": role_name,
                         "formatted_content": role_value_str
                     })
            else:
                log.warning(f"Skipping invalid custom_role definition (expecting 'role' and 'value' keys): {role_def}")

    messages = form_data.get("messages", [])

    if target_backend == "ollama":
        combined_content_parts = []
        if formatted_system_prompt:
            combined_content_parts.append(formatted_system_prompt)

        for role_info in processed_custom_roles:
            combined_content_parts.append(f"[{role_info['name'].upper()}]:\n{role_info['formatted_content']}")

        combined_content = "\n\n".join(combined_content_parts).strip()

        if combined_content:
            messages = add_or_update_system_message(combined_content, messages)
        elif not messages:
             messages = []

    else: # OpenAI/Compatible
        initial_messages = []
        if formatted_system_prompt:
            initial_messages.append({"role": "system", "content": formatted_system_prompt})

        if processed_custom_roles:
            for role_info in processed_custom_roles:
                 initial_messages.append({
                      "role": role_info["name"],
                      "content": role_info["formatted_content"]
                 })

        if initial_messages:
            existing_role_names = {"system"} | {role_info['name'] for role_info in processed_custom_roles}
            non_initial_messages = [msg for msg in messages if msg.get("role") not in existing_role_names]
            messages = initial_messages + non_initial_messages
        elif not messages:
            messages = []

    form_data["messages"] = messages
    return form_data


# inplace function: form_data is modified
def apply_model_params_to_body(
    params: dict, form_data: dict, mappings: dict[str, Callable]
) -> dict:
    if not params:
        return form_data

    for key, cast_func in mappings.items():
        if (value := params.get(key)) is not None:
            form_data[key] = cast_func(value)

    return form_data


# inplace function: form_data is modified
def apply_model_params_to_body_openai(params: dict, form_data: dict) -> dict:
    mappings = {
        "temperature": float,
        "top_p": float,
        "max_tokens": int,
        "frequency_penalty": float,
        "reasoning_effort": str,
        "seed": lambda x: x,
        "stop": lambda x: [bytes(s, "utf-8").decode("unicode_escape") for s in x],
        "logit_bias": lambda x: x,
        "response_format": dict,
    }
    return apply_model_params_to_body(params, form_data, mappings)


def apply_model_params_to_body_ollama(params: dict, form_data: dict) -> dict:
    # Convert OpenAI parameter names to Ollama parameter names if needed.
    name_differences = {
        "max_tokens": "num_predict",
    }

    # Create a copy to modify for this function scope if name differences exist
    local_params = params.copy() if name_differences.keys() & params.keys() else params

    for key, value in name_differences.items():
        if (param := local_params.get(key, None)) is not None:
            # Copy the parameter to new name then delete it, to prevent Ollama warning of invalid option provided
            local_params[value] = local_params[key]
            del local_params[key]

    # See https://github.com/ollama/ollama/blob/main/docs/api.md#request-8
    mappings = {
        "temperature": float,
        "top_p": float,
        "seed": lambda x: x,
        "mirostat": int,
        "mirostat_eta": float,
        "mirostat_tau": float,
        "num_ctx": int,
        "num_batch": int,
        "num_keep": int,
        "num_predict": int,
        "repeat_last_n": int,
        "top_k": int,
        "min_p": float,
        "typical_p": float,
        "repeat_penalty": float,
        "presence_penalty": float,
        "frequency_penalty": float,
        "penalize_newline": bool,
        "stop": lambda x: [bytes(s, "utf-8").decode("unicode_escape") for s in x],
        "numa": bool,
        "num_gpu": int,
        "main_gpu": int,
        "low_vram": bool,
        "vocab_only": bool,
        "use_mmap": bool,
        "use_mlock": bool,
        "num_thread": int,
    }

    # Extract keep_alive from options if it exists
    if "options" in form_data and "keep_alive" in form_data["options"]:
        form_data["keep_alive"] = form_data["options"]["keep_alive"]
        del form_data["options"]["keep_alive"]

    if "options" in form_data and "format" in form_data["options"]:
        form_data["format"] = form_data["options"]["format"]
        del form_data["options"]["format"]

    # Use local_params for applying to body
    return apply_model_params_to_body(local_params, form_data, mappings)


def convert_messages_openai_to_ollama(messages: list[dict]) -> list[dict]:
    ollama_messages = []

    for message in messages:
        # Initialize the new message structure with the role
        new_message = {"role": message["role"]}

        content = message.get("content", None) # Changed default to None for clarity
        tool_calls = message.get("tool_calls", None)
        tool_call_id = message.get("tool_call_id", None)

        # Check if the content is a string (just a simple message)
        if isinstance(content, str):
            # If the content is a string, it's pure text
            new_message["content"] = content

            # If message is a tool call response, add the tool call id to the message
            if tool_call_id:
                # Ollama expects role 'tool' for tool responses
                new_message["role"] = "tool"
                new_message["tool_call_id"] = tool_call_id

        elif tool_calls:
             # Ollama expects role 'assistant' for tool *calls*
            new_message["role"] = "assistant"
            ollama_tool_calls = []
            for tool_call in tool_calls:
                # Arguments need to be a dict for Ollama, not a string
                arguments_dict = {}
                try:
                    # Ensure arguments is a string before trying to load
                    func_args = tool_call.get("function", {}).get("arguments", "{}")
                    if isinstance(func_args, str):
                         arguments_dict = json.loads(func_args)
                    elif isinstance(func_args, dict): # If it's already a dict
                         arguments_dict = func_args
                except json.JSONDecodeError:
                    log.error(f"Could not decode tool call arguments: {func_args}")
                    arguments_dict = {} # Default to empty dict on error

                ollama_tool_call = {
                    "type": "function", # Ollama uses 'type'
                    # Ollama doesn't use index or id directly in the call structure
                    "function": {
                        "name": tool_call.get("function", {}).get("name", ""),
                        "arguments": arguments_dict,
                    },
                }
                ollama_tool_calls.append(ollama_tool_call)
            new_message["tool_calls"] = ollama_tool_calls
            # Content must be explicitly null or empty string when tool_calls are present for Ollama
            new_message["content"] = ""


        elif isinstance(content, list):
            # Assume the content is a list of dicts (e.g., text + image)
            content_text = ""
            images = []

            # Iterate through the list of content items
            for item in content:
                # Check if it's a text type
                if item.get("type") == "text":
                    content_text += item.get("text", "")

                # Check if it's an image URL type
                elif item.get("type") == "image_url":
                    img_url = item.get("image_url", {}).get("url", "")
                    if img_url:
                        # If the image url starts with data:, it's a base64 image and should be trimmed
                        if img_url.startswith("data:"):
                            # Keep only the base64 part
                            try:
                                img_url = img_url.split(",", 1)[1]
                            except IndexError:
                                log.warning(f"Could not split base64 image data URL: {img_url[:50]}...")
                                continue # Skip this invalid image url
                        images.append(img_url)

            # Add content text (if any)
            if content_text:
                new_message["content"] = content_text.strip()
            # If only images were present, content might be None, ensure it's at least "" if needed
            elif images and 'content' not in new_message:
                 new_message['content'] = ""


            # Add images (if any)
            if images:
                new_message["images"] = images

        # Ensure 'content' key exists if it wasn't set (Ollama requires it, even if empty)
        if 'content' not in new_message and 'tool_calls' not in new_message:
             new_message['content'] = ""


        # Append the new formatted message to the result
        ollama_messages.append(new_message)

    return ollama_messages


def convert_payload_openai_to_ollama(openai_payload: dict) -> dict:
    """
    Converts a payload formatted for OpenAI's API to be compatible with Ollama's API endpoint for chat completions.

    Args:
        openai_payload (dict): The payload originally designed for OpenAI API usage.

    Returns:
        dict: A modified payload compatible with the Ollama API.
    """
    ollama_payload = {}

    # Mapping basic model and message details
    ollama_payload["model"] = openai_payload.get("model")
    ollama_payload["messages"] = convert_messages_openai_to_ollama(
        openai_payload.get("messages")
    )
    ollama_payload["stream"] = openai_payload.get("stream", False)

    if "tools" in openai_payload:
        ollama_payload["tools"] = openai_payload["tools"]

    if "format" in openai_payload:
        ollama_payload["format"] = openai_payload["format"]

    # If there are advanced parameters in the payload, format them in Ollama's options field
    if openai_payload.get("options"):
        ollama_payload["options"] = openai_payload["options"]
        ollama_options = openai_payload["options"]

        # Re-Mapping OpenAI's `max_tokens` -> Ollama's `num_predict`
        if "max_tokens" in ollama_options:
            ollama_options["num_predict"] = ollama_options["max_tokens"]
            del ollama_options[
                "max_tokens"
            ]  # To prevent Ollama warning of invalid option provided

        # Ollama lacks a "system" prompt option. It has to be provided as a direct parameter, so we copy it down.
        if "system" in ollama_options:
            ollama_payload["system"] = ollama_options["system"]
            del ollama_options[
                "system"
            ]  # To prevent Ollama warning of invalid option provided

        # Extract keep_alive from options if it exists
        if "keep_alive" in ollama_options:
            ollama_payload["keep_alive"] = ollama_options["keep_alive"]
            del ollama_options["keep_alive"]

    # If there is the "stop" parameter in the openai_payload, remap it to the ollama_payload.options
    if "stop" in openai_payload:
        ollama_options = ollama_payload.get("options", {})
        ollama_options["stop"] = openai_payload.get("stop")
        ollama_payload["options"] = ollama_options

    if "metadata" in openai_payload:
        ollama_payload["metadata"] = openai_payload["metadata"]

    if "response_format" in openai_payload:
        response_format = openai_payload["response_format"]
        format_type = response_format.get("type", None)

        schema = response_format.get(format_type, None)
        if schema:
            format = schema.get("schema", None)
            ollama_payload["format"] = format

    return ollama_payload