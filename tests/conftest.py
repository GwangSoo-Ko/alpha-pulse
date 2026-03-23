"""Shared test fixtures for AlphaPulse."""

import os

# Ensure tests don't accidentally use real API keys
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "test-chat-id")
