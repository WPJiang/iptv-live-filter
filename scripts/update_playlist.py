#!/usr/bin/env python3
"""Generate a Televizo-friendly IPTV playlist from public iptv-org sources."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
import re
import requests
from urllib.parse import urlparse

ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)="([^"]*)"')
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class ChannelEntry:
    source: str
    extinf: str
    attrs: dict[str, str]
    name: str
    url: str


def sanitize_text(value: str) -> str:
    cleaned = CONTROL_RE.sub("", value)
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    return " ".join(cleaned.split())


def parse_extinf(line: str) -> tuple[dict[str, str], str]:
    attrs = {match.group(1): sanitize_text(match.group(2)) for match in ATTR_RE.finditer(line)}
    if "," not in line:
        return attrs, ""
    name = sanitize_text(line.rsplit(",", 1)[1])
    return attrs, name


def parse_m3u(content: str, source: str) -> list[ChannelEntry]:
    entries: list[ChannelEntry] = []
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("#EXTINF"):
            index += 1
            continue

        next_index = index + 1
        if next_index >= len(lines) or lines[next_index].startswith("#"):
            index += 1
            continue

        url = sanitize_text(lines[next_index])
        attrs, name = parse_extinf(line)
        entries.append(ChannelEntry(source=source, extinf=line, attrs=attrs, name=name, url=url))
        index = next_index + 1

    return entries


def format_extinf(entry: ChannelEntry) -> str:
    parts = ["#EXTINF:-1"]
    for key in ("tvg-id", "tvg-name", "tvg-logo", "group-title"):
        value = entry.attrs.get(key)
        if value:
            safe_value = sanitize_text(value).replace('"', "'")
            parts.append(f'{key}="{safe_value}"')
    safe_name = sanitize_text(entry.name).replace('"', "'")
    return f'{" ".join(parts)},{safe_name}'


UNSUPPORTED_SCHEMES = {"rtp", "udp", "rtsp"}


def is_multicast_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    try:
        return ip_address(hostname).is_multicast
    except ValueError:
        return False


def skip_reason(entry: ChannelEntry) -> str | None:
    parsed = urlparse(entry.url)
    scheme = parsed.scheme.lower()
    if scheme in UNSUPPORTED_SCHEMES:
        return "unsupported_protocol"
    if scheme not in {"http", "https"}:
        return "unsupported_protocol"
    if is_multicast_host(parsed.hostname):
        return "multicast_address"
    return None


def dedupe_entries(entries: list[ChannelEntry]) -> list[ChannelEntry]:
    seen: set[tuple[str, str]] = set()
    result: list[ChannelEntry] = []
    for entry in entries:
        key = (sanitize_text(entry.name).casefold(), sanitize_text(entry.url))
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def write_playlist(path: Path, entries: list[ChannelEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#EXTM3U"]
    for entry in entries:
        lines.append(format_extinf(entry))
        lines.append(sanitize_text(entry.url))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


USER_AGENT = "Mozilla/5.0 (compatible; iptv-live-filter/1.0; +https://github.com/)"
HLS_MARKERS = ("#EXTM3U", "#EXT-X-STREAM-INF", "#EXT-X-TARGETDURATION", ".ts", ".m4s")
STREAM_CONTENT_TYPES = (
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "audio/mpegurl",
    "video/mp2t",
    "video/",
    "application/octet-stream",
)


@dataclass(frozen=True)
class ProbeResult:
    entry: ChannelEntry
    ok: bool
    reason: str


def looks_like_hls(text: str) -> bool:
    sample = text[:4096]
    return any(marker in sample for marker in HLS_MARKERS)


def has_stream_content_type(content_type: str) -> bool:
    lowered = content_type.lower()
    return any(marker in lowered for marker in STREAM_CONTENT_TYPES)


def probe_entry(entry: ChannelEntry, session: requests.Session | None = None, timeout: int = 8) -> ProbeResult:
    active_session = session or requests.Session()
    try:
        response = active_session.get(
            entry.url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            stream=False,
        )
    except requests.RequestException as exc:
        return ProbeResult(entry=entry, ok=False, reason=exc.__class__.__name__.lower())

    if response.status_code < 200 or response.status_code >= 400:
        return ProbeResult(entry=entry, ok=False, reason=f"http_{response.status_code}")

    content_type = response.headers.get("content-type", "")
    if entry.url.lower().split("?", 1)[0].endswith(".m3u8"):
        if looks_like_hls(response.text):
            return ProbeResult(entry=entry, ok=True, reason="ok")
        return ProbeResult(entry=entry, ok=False, reason="invalid_hls")

    if looks_like_hls(response.text) or has_stream_content_type(content_type):
        return ProbeResult(entry=entry, ok=True, reason="ok")

    return ProbeResult(entry=entry, ok=False, reason="unsupported_content")


def main() -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
