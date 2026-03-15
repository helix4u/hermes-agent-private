"""
DeepSeek V3 tool call parser.

Format uses special unicode tokens:
    <｜tool▁calls▁begin｜>
    <｜tool▁call▁begin｜>type<｜tool▁sep｜>function_name
    ```json
    {"arg": "value"}
    ```
    <｜tool▁call▁end｜>
    <｜tool▁calls▁end｜>

Based on VLLM's DeepSeekV3ToolParser.extract_tool_calls()
"""

import logging
import re
import uuid
from typing import List, Optional

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

from environments.tool_call_parsers import ParseResult, ToolCallParser, register_parser

logger = logging.getLogger(__name__)


@register_parser("deepseek_v3")
class DeepSeekV3ToolCallParser(ToolCallParser):
    """
    Parser for DeepSeek V3 tool calls.

    Uses special unicode tokens with fullwidth angle brackets and block elements.
    Extracts type, function name, and JSON arguments from the structured format.
    Ensures multiple adjacent tool calls are all captured independently.
    """

    START_TOKEN = "<｜tool▁calls▁begin｜>"

    # Use non-greedy captures and flexible whitespace so adjacent tool-call
    # blocks do not collapse into one oversized match.
    PATTERN = re.compile(
        r"<｜tool▁call▁begin｜>(?P<type>.*?)<｜tool▁sep｜>(?P<function_name>.*?)\s*```json\s*(?P<function_arguments>.*?)\s*```\s*<｜tool▁call▁end｜>",
        re.DOTALL,
    )

    def parse(self, text: str) -> ParseResult:
        if self.START_TOKEN not in text:
            return text, None

        try:
            matches = list(self.PATTERN.finditer(text))
            if not matches:
                return text, None

            tool_calls: List[ChatCompletionMessageToolCall] = []
            for match in matches:
                tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        type="function",
                        function=Function(
                            name=match.group("function_name").strip(),
                            arguments=match.group("function_arguments").strip(),
                        ),
                    )
                )

            if not tool_calls:
                return text, None

            # Content is everything before the tool calls section.
            content = text[: text.find(self.START_TOKEN)].strip()
            return content if content else None, tool_calls

        except Exception as exc:
            logger.error("Error parsing DeepSeek V3 tool calls: %s", exc)
            return text, None
