from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class CommandType(Enum):
    RESET = "reset"
    WEB = "web"
    SUMMARIZE = "summarize"
    FOCUS = "focus"
    PIN = "pin"
    UNPIN = "unpin"
    SEARCH = "search"
    HELP = "help"
    CLEAR = "clear"
    EXPORT = "export"
    CUSTOM = "custom"


@dataclass
class SlashCommand:
    command_type: CommandType
    raw_input: str
    args: List[str] = field(default_factory=list)
    kwargs: Dict[str, str] = field(default_factory=dict)
    cleaned_query: str = ""

    @property
    def name(self) -> str:
        return self.command_type.value


@dataclass
class CommandResult:
    success: bool
    command: SlashCommand
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "command": self.command.name,
            "message": self.message,
            "data": self.data,
            "actions": self.actions,
        }


class SlashCommandParser:
    COMMAND_PATTERNS = {
        CommandType.RESET: [r"/reset", r"/clear\s*history", r"/new"],
        CommandType.WEB: [r"/web", r"/browse", r"/search\s+web"],
        CommandType.SUMMARIZE: [r"/summarize", r"/summary", r"/sum"],
        CommandType.FOCUS: [r"/focus\s+(.+)", r"/pin\s+doc\s+(.+)"],
        CommandType.PIN: [r"/pin\s+(.+)", r"/pin"],
        CommandType.UNPIN: [r"/unpin\s*(.*)", r"/unfocus\s*(.*)"],
        CommandType.SEARCH: [r"/search\s+(.+)", r"/find\s+(.+)"],
        CommandType.HELP: [r"/help", r"/\?", r"/commands"],
        CommandType.CLEAR: [r"/clear", r"/cls"],
        CommandType.EXPORT: [r"/export\s*(.*)", r"/save\s*(.*)"],
    }

    def __init__(self):
        self._custom_commands: Dict[str, Callable] = {}
        self._command_handlers: Dict[CommandType, Callable] = {}

    def register_handler(self, command_type: CommandType, handler: Callable) -> None:
        self._command_handlers[command_type] = handler

    def register_custom_command(self, name: str, handler: Callable) -> None:
        self._custom_commands[name.lower()] = handler

    def parse(self, user_input: str) -> Tuple[SlashCommand, str]:
        cleaned_input = user_input.strip()

        if not cleaned_input.startswith("/"):
            return SlashCommand(
                command_type=CommandType.CUSTOM,
                raw_input=user_input,
                cleaned_query=user_input,
            ), user_input

        for command_type, patterns in self.COMMAND_PATTERNS.items():
            for pattern in patterns:
                match = re.match(pattern, cleaned_input, re.IGNORECASE)
                if match:
                    args = list(match.groups()) if match.groups() else []
                    kwargs = self._parse_kwargs(cleaned_input)

                    remaining = cleaned_input[match.end() :].strip()

                    return SlashCommand(
                        command_type=command_type,
                        raw_input=user_input,
                        args=args,
                        kwargs=kwargs,
                        cleaned_query=remaining,
                    ), remaining

        first_word = cleaned_input.split()[0] if cleaned_input.split() else ""
        custom_name = first_word[1:].lower() if first_word.startswith("/") else ""

        return SlashCommand(
            command_type=CommandType.CUSTOM,
            raw_input=user_input,
            args=[custom_name] if custom_name else [],
            cleaned_query=user_input,
        ), user_input

    def execute(
        self,
        command: SlashCommand,
        context: Optional[Dict[str, Any]] = None,
    ) -> CommandResult:
        context = context or {}

        if command.command_type in self._command_handlers:
            try:
                return self._command_handlers[command.command_type](command, context)
            except Exception as e:
                return CommandResult(
                    success=False,
                    command=command,
                    message=f"Command execution failed: {str(e)}",
                )

        if command.command_type == CommandType.HELP:
            return self._handle_help(command)

        if command.command_type == CommandType.CUSTOM:
            custom_name = command.args[0] if command.args else ""
            if custom_name in self._custom_commands:
                try:
                    return self._custom_commands[custom_name](command, context)
                except Exception as e:
                    return CommandResult(
                        success=False,
                        command=command,
                        message=f"Custom command '{custom_name}' failed: {str(e)}",
                    )

        return CommandResult(
            success=False,
            command=command,
            message=f"Unknown command: {command.name}",
        )

    def _parse_kwargs(self, text: str) -> Dict[str, str]:
        kwargs = {}
        kwarg_pattern = r"--(\w+)[=:\s]+(\S+)"
        for match in re.finditer(kwarg_pattern, text):
            kwargs[match.group(1)] = match.group(2)
        return kwargs

    def _handle_help(self, command: SlashCommand) -> CommandResult:
        help_text = """
Available Slash Commands:
  /reset, /new        - Reset conversation history
  /web, /browse       - Enable web browsing mode
  /summarize, /sum    - Summarize current context
  /focus <doc>        - Focus on specific document
  /pin [doc]          - Pin document to context
  /unpin [doc]        - Unpin document from context
  /search <query>     - Search in knowledge base
  /help, /commands    - Show this help message
  /clear, /cls        - Clear screen
  /export [filename]  - Export conversation

Custom commands can be registered via API.
"""
        return CommandResult(
            success=True,
            command=command,
            message=help_text.strip(),
            data={"commands": [ct.value for ct in CommandType]},
        )

    def get_available_commands(self) -> List[str]:
        builtin = [ct.value for ct in CommandType if ct != CommandType.CUSTOM]
        custom = list(self._custom_commands.keys())
        return builtin + custom
