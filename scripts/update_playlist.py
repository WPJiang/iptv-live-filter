#!/usr/bin/env python3
"""Generate a Televizo-friendly IPTV playlist from public iptv-org sources."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
import argparse
import json
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
DRM_OR_AUTH_MARKERS = (
    "/drm/",
    ";session=",
    "acl=",
    "auth=",
    "authid=",
    "exp=",
    "expires=",
    "hdntl=",
    "hdnts=",
    "hmac=",
    "key=",
    "session=",
    "signature=",
    "sig=",
    "token=",
)


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
    lowered_url = entry.url.lower()
    if any(marker in lowered_url for marker in DRM_OR_AUTH_MARKERS):
        return "drm_or_auth_required"
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
DEFAULT_SOURCES = ["cn", "hk", "mo", "tw", "us"]
SOURCE_URL_TEMPLATE = "https://iptv-org.github.io/iptv/countries/{source}.m3u"


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


MAX_RESPONSE_BYTES = 256 * 1024


def read_response_sample(response, max_bytes: int = MAX_RESPONSE_BYTES) -> str:
    chunks: list[str] = []
    total = 0
    for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
        if not chunk:
            continue
        if isinstance(chunk, bytes):
            text = chunk.decode("utf-8", errors="replace")
        else:
            text = chunk
        total += len(text.encode("utf-8", errors="ignore"))
        chunks.append(text)
        if total >= max_bytes:
            break
    return "".join(chunks)


def probe_entry(entry: ChannelEntry, session: requests.Session | None = None, timeout: int = 8) -> ProbeResult:
    active_session = session or requests.Session()
    try:
        response = active_session.get(
            entry.url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            stream=True,
        )
    except requests.RequestException as exc:
        return ProbeResult(entry=entry, ok=False, reason=exc.__class__.__name__.lower())

    if response.status_code < 200 or response.status_code >= 400:
        return ProbeResult(entry=entry, ok=False, reason=f"http_{response.status_code}")

    content_type = response.headers.get("content-type", "")
    sample = read_response_sample(response)
    if entry.url.lower().split("?", 1)[0].endswith(".m3u8"):
        if looks_like_hls(sample):
            return ProbeResult(entry=entry, ok=True, reason="ok")
        return ProbeResult(entry=entry, ok=False, reason="invalid_hls")

    if looks_like_hls(sample) or has_stream_content_type(content_type):
        return ProbeResult(entry=entry, ok=True, reason="ok")

    return ProbeResult(entry=entry, ok=False, reason="unsupported_content")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_source_playlist(source: str, timeout: int = 20) -> str:
    url = SOURCE_URL_TEMPLATE.format(source=source)
    response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def write_report(
    path: Path,
    sources: list[str],
    total_channels: int,
    passed: list[ChannelEntry],
    failed: list[ProbeResult],
    skipped: list[tuple[ChannelEntry, str]],
    source_errors: dict[str, str],
    generated_at: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": generated_at,
        "sources": sources,
        "total_channels": total_channels,
        "passed": len(passed),
        "failed": len(failed),
        "skipped": len(skipped),
        "source_errors": source_errors,
        "failures": [
            {"name": result.entry.name, "url": result.entry.url, "reason": result.reason}
            for result in failed[:500]
        ],
        "skips": [
            {"name": entry.name, "url": entry.url, "reason": reason}
            for entry, reason in skipped[:500]
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def probe_entries(entries: list[ChannelEntry], timeout: int, workers: int) -> list[ProbeResult]:
    results: list[ProbeResult | None] = [None] * len(entries)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(probe_entry, entry, None, timeout): index
            for index, entry in enumerate(entries)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return [result for result in results if result is not None]


def generate_outputs(
    output_dir: Path,
    sources: list[str],
    fetch_playlist=fetch_source_playlist,
    probe=None,
    timeout: int = 8,
    workers: int = 12,
    generated_at: str | None = None,
) -> int:
    generated = generated_at or utc_now_iso()
    entries: list[ChannelEntry] = []
    source_errors: dict[str, str] = {}

    for source in sources:
        try:
            content = fetch_playlist(source)
        except Exception as exc:
            source_errors[source] = str(exc)
            continue
        entries.extend(parse_m3u(content, source=source))

    total_channels = len(entries)
    skipped: list[tuple[ChannelEntry, str]] = []
    candidates: list[ChannelEntry] = []
    for entry in entries:
        reason = skip_reason(entry)
        if reason:
            skipped.append((entry, reason))
        else:
            candidates.append(entry)

    candidates = dedupe_entries(candidates)
    if probe is None:
        probe_results = probe_entries(candidates, timeout=timeout, workers=workers)
    else:
        probe_results = [probe(entry) for entry in candidates]

    passed = [result.entry for result in probe_results if result.ok]
    failed = [result for result in probe_results if not result.ok]

    report_path = output_dir / "report.json"
    write_report(
        report_path,
        sources=sources,
        total_channels=total_channels,
        passed=passed,
        failed=failed,
        skipped=skipped,
        source_errors=source_errors,
        generated_at=generated,
    )

    if not passed:
        return 1

    write_playlist(output_dir / "live.m3u", passed)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate filtered IPTV playlist from iptv-org.")
    parser.add_argument("--output-dir", default="public", type=Path)
    parser.add_argument("--sources", default=",".join(DEFAULT_SOURCES), help="Comma-separated country codes")
    parser.add_argument("--timeout", default=8, type=int)
    parser.add_argument("--workers", default=12, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = [source.strip() for source in args.sources.split(",") if source.strip()]
    return generate_outputs(
        output_dir=args.output_dir,
        sources=sources,
        timeout=args.timeout,
        workers=args.workers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
