from __future__ import annotations

from typing import Any, Dict

from cognitive_os.commands.slash_parser import CommandResult, CommandType, SlashCommand


class BuiltinCommands:
    @staticmethod
    def handle_reset(command: SlashCommand, context: Dict[str, Any]) -> CommandResult:
        session_id = context.get("session_id")
        chat_history = context.get("chat_history")

        if session_id and chat_history:
            chat_history.delete_session(session_id)
            return CommandResult(
                success=True,
                command=command,
                message="Conversation history has been reset.",
                actions=["reset_history"],
                data={"session_id": session_id},
            )

        return CommandResult(
            success=True,
            command=command,
            message="Conversation context cleared.",
            actions=["clear_context"],
        )

    @staticmethod
    def handle_web(command: SlashCommand, context: Dict[str, Any]) -> CommandResult:
        return CommandResult(
            success=True,
            command=command,
            message="Web browsing mode enabled. I can now search the web for information.",
            actions=["enable_web_browsing"],
            data={"web_mode": True},
        )

    @staticmethod
    def handle_summarize(command: SlashCommand, context: Dict[str, Any]) -> CommandResult:
        retrieved = context.get("retrieved", [])
        if not retrieved:
            return CommandResult(
                success=False,
                command=command,
                message="No context available to summarize.",
            )

        summary_parts = []
        for i, item in enumerate(retrieved[:5], 1):
            topic = item.get("topic", "Unknown")
            text = item.get("text", "")[:100]
            summary_parts.append(f"{i}. {topic}: {text}...")

        return CommandResult(
            success=True,
            command=command,
            message="Context summary:\n" + "\n".join(summary_parts),
            actions=["summarize"],
            data={"context_count": len(retrieved)},
        )

    @staticmethod
    def handle_focus(command: SlashCommand, context: Dict[str, Any]) -> CommandResult:
        if not command.args:
            return CommandResult(
                success=False,
                command=command,
                message="Please specify a document to focus on. Usage: /focus <document_name>",
            )

        doc_name = command.args[0]
        return CommandResult(
            success=True,
            command=command,
            message=f"Focused on document: {doc_name}",
            actions=["focus_document"],
            data={"focus_document": doc_name},
        )

    @staticmethod
    def handle_pin(command: SlashCommand, context: Dict[str, Any]) -> CommandResult:
        doc_name = command.args[0] if command.args else None

        if doc_name:
            return CommandResult(
                success=True,
                command=command,
                message=f"Document '{doc_name}' pinned to context.",
                actions=["pin_document"],
                data={"pin_document": doc_name},
            )
        else:
            return CommandResult(
                success=True,
                command=command,
                message="Current context pinned.",
                actions=["pin_context"],
            )

    @staticmethod
    def handle_unpin(command: SlashCommand, context: Dict[str, Any]) -> CommandResult:
        doc_name = command.args[0] if command.args else None

        if doc_name:
            return CommandResult(
                success=True,
                command=command,
                message=f"Document '{doc_name}' unpinned from context.",
                actions=["unpin_document"],
                data={"unpin_document": doc_name},
            )
        else:
            return CommandResult(
                success=True,
                command=command,
                message="All pinned documents unpinned.",
                actions=["unpin_all"],
            )

    @staticmethod
    def handle_search(command: SlashCommand, context: Dict[str, Any]) -> CommandResult:
        if not command.args:
            return CommandResult(
                success=False,
                command=command,
                message="Please provide a search query. Usage: /search <query>",
            )

        query = command.args[0]
        toolkit = context.get("toolkit")
        knowledge_base_id = context.get("knowledge_base_id")

        if toolkit:
            results = toolkit.retrieve_knowledge(query, top_k=5, knowledge_base_id=knowledge_base_id)
            return CommandResult(
                success=True,
                command=command,
                message=f"Found {len(results)} results for '{query}'",
                actions=["search"],
                data={"query": query, "results": results},
            )

        return CommandResult(
            success=False,
            command=command,
            message="Search tool not available in current context.",
        )

    @staticmethod
    def handle_clear(command: SlashCommand, context: Dict[str, Any]) -> CommandResult:
        return CommandResult(
            success=True,
            command=command,
            message="Screen cleared.",
            actions=["clear_screen"],
        )

    @staticmethod
    def handle_export(command: SlashCommand, context: Dict[str, Any]) -> CommandResult:
        filename = command.args[0] if command.args else "conversation.txt"
        return CommandResult(
            success=True,
            command=command,
            message=f"Conversation exported to {filename}",
            actions=["export"],
            data={"filename": filename},
        )

    @classmethod
    def register_handlers(cls, parser) -> None:
        parser.register_handler(CommandType.RESET, cls.handle_reset)
        parser.register_handler(CommandType.WEB, cls.handle_web)
        parser.register_handler(CommandType.SUMMARIZE, cls.handle_summarize)
        parser.register_handler(CommandType.FOCUS, cls.handle_focus)
        parser.register_handler(CommandType.PIN, cls.handle_pin)
        parser.register_handler(CommandType.UNPIN, cls.handle_unpin)
        parser.register_handler(CommandType.SEARCH, cls.handle_search)
        parser.register_handler(CommandType.CLEAR, cls.handle_clear)
        parser.register_handler(CommandType.EXPORT, cls.handle_export)

    @staticmethod
    def list_commands() -> list:
        return [
            {"name": "/reset", "description": "Reset conversation history"},
            {"name": "/web", "description": "Enable web browsing mode"},
            {"name": "/summarize", "description": "Summarize current context"},
            {"name": "/focus <doc>", "description": "Focus on specific document"},
            {"name": "/pin [doc]", "description": "Pin document to context"},
            {"name": "/unpin [doc]", "description": "Unpin document from context"},
            {"name": "/search <query>", "description": "Search in knowledge base"},
            {"name": "/help", "description": "Show help message"},
            {"name": "/clear", "description": "Clear screen"},
            {"name": "/export [filename]", "description": "Export conversation"},
        ]
