import json
import logging
import re
import ssl
from pathlib import Path
from urllib.request import urlopen

import certifi
import feedparser

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_cfg = Config()


class PostDetector:
    def __init__(self, blog_id: str = _cfg.BLOG_ID, state_file: str = _cfg.STATE_FILE):
        self.blog_id = blog_id
        self.state_file = Path(state_file)
        self.rss_url = f"https://rss.blog.naver.com/{blog_id}.xml"

    def fetch_new_posts(self, force_latest: int = 0) -> list[dict]:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        response = urlopen(self.rss_url, context=ssl_context)
        feed = feedparser.parse(response)
        if feed.bozo:
            logger.error(f"RSS 파싱 실패: {feed.bozo_exception}")
            return []

        state = self._load_state()
        seen_ids = set(state.get("seen_ids", []))
        posts = []

        entries = feed.entries
        if force_latest > 0:
            entries = entries[:force_latest]

        for entry in entries:
            log_no = self._extract_log_no(entry.link)
            if not log_no:
                continue
            if log_no in seen_ids and force_latest == 0:
                continue

            category = None
            if hasattr(entry, "tags") and entry.tags:
                category = entry.tags[0].term

            posts.append({
                "id": log_no,
                "title": entry.title,
                "link": entry.link,
                "published": entry.get("published", ""),
                "summary_rss": entry.get("summary", ""),
                "category": category,
            })

        return posts

    def mark_seen(self, log_no: str):
        self._mark_seen(log_no)

    def _extract_log_no(self, url: str) -> str | None:
        match = re.search(r"/(\d+)(?:\?|$)", url)
        return match.group(1) if match else None

    def _mark_seen(self, log_no: str):
        state = self._load_state()
        seen = state.get("seen_ids", [])
        if log_no not in seen:
            seen.append(log_no)
        state["seen_ids"] = seen[-200:]
        self._save_state(state)

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, IOError):
                return {"seen_ids": []}
        return {"seen_ids": []}

    def _save_state(self, state: dict):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
