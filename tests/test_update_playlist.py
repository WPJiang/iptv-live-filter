from scripts import update_playlist


SAMPLE_M3U = """#EXTM3U
#EXTINF:-1 tvg-id="CCTV1.cn" tvg-name="CCTV-1" tvg-logo="https://logo.example/cctv1.png" group-title="China",CCTV-1 综合\n
https://example.com/cctv1.m3u8
#EXTINF:-1 group-title="Hong Kong",RTHK TV 31
https://example.com/rthk.m3u8
#EXTINF:-1,Broken Without URL
#EXTINF:-1 group-title="Taiwan",Taiwan News
https://example.com/tw.m3u8
"""


def test_parse_m3u_extracts_extinf_and_url_pairs():
    entries = update_playlist.parse_m3u(SAMPLE_M3U, source="cn")

    assert len(entries) == 3
    assert entries[0].source == "cn"
    assert entries[0].name == "CCTV-1 综合"
    assert entries[0].url == "https://example.com/cctv1.m3u8"
    assert entries[0].attrs["tvg-id"] == "CCTV1.cn"
    assert entries[0].attrs["tvg-name"] == "CCTV-1"
    assert entries[0].attrs["tvg-logo"] == "https://logo.example/cctv1.png"
    assert entries[0].attrs["group-title"] == "China"
    assert entries[1].name == "RTHK TV 31"
    assert entries[2].name == "Taiwan News"


def test_sanitize_text_removes_control_characters_and_line_breaks():
    assert update_playlist.sanitize_text(" CCTV\x00-1\r\n综合 ") == "CCTV-1 综合"


def test_format_extinf_preserves_metadata_and_sanitizes_name():
    entry = update_playlist.ChannelEntry(
        source="cn",
        extinf="#EXTINF:-1 tvg-id=\"CCTV1.cn\" group-title=\"China\",CCTV\x00-1",
        attrs={"tvg-id": "CCTV1.cn", "group-title": "China"},
        name="CCTV\x00-1",
        url="https://example.com/cctv1.m3u8",
    )

    line = update_playlist.format_extinf(entry)

    assert line == '#EXTINF:-1 tvg-id="CCTV1.cn" group-title="China",CCTV-1'


def make_entry(url: str, name: str = "Test") -> update_playlist.ChannelEntry:
    return update_playlist.ChannelEntry(
        source="cn",
        extinf=f"#EXTINF:-1,{name}",
        attrs={},
        name=name,
        url=url,
    )


def test_skip_reason_rejects_unsupported_protocols():
    assert update_playlist.skip_reason(make_entry("rtp://239.3.1.1:8000")) == "unsupported_protocol"
    assert update_playlist.skip_reason(make_entry("udp://239.3.1.1:8000")) == "unsupported_protocol"
    assert update_playlist.skip_reason(make_entry("rtsp://example.com/live")) == "unsupported_protocol"


def test_skip_reason_rejects_multicast_http_hosts():
    assert update_playlist.skip_reason(make_entry("http://239.3.1.1:8000/live")) == "multicast_address"
    assert update_playlist.skip_reason(make_entry("http://224.0.0.1/live")) == "multicast_address"


def test_skip_reason_allows_public_http_and_https():
    assert update_playlist.skip_reason(make_entry("https://example.com/live.m3u8")) is None
    assert update_playlist.skip_reason(make_entry("http://example.com/live.m3u8")) is None


def test_skip_reason_rejects_non_http_urls():
    assert update_playlist.skip_reason(make_entry("ftp://example.com/live")) == "unsupported_protocol"
    assert update_playlist.skip_reason(make_entry("not-a-url")) == "unsupported_protocol"


def test_skip_reason_rejects_drm_or_auth_looking_urls():
    assert update_playlist.skip_reason(make_entry("https://example.com/drm/channel.m3u8")) == "drm_or_auth_required"
    assert update_playlist.skip_reason(make_entry("https://example.com/live.m3u8?auth=testpub")) == "drm_or_auth_required"
    assert update_playlist.skip_reason(make_entry("https://example.com/live.m3u8?key=txiptv")) == "drm_or_auth_required"
    assert update_playlist.skip_reason(make_entry("https://example.com/live.m3u8?hdnts=st=1~exp=2~acl=*~hmac=abc")) == "drm_or_auth_required"
    assert update_playlist.skip_reason(make_entry("https://example.com/live;session=abc/index.m3u8")) == "drm_or_auth_required"


def test_dedupe_entries_removes_exact_name_url_duplicates_only():
    first = make_entry("https://example.com/a.m3u8", "CCTV-1")
    duplicate = make_entry("https://example.com/a.m3u8", " CCTV-1 ")
    alternate = make_entry("https://example.com/b.m3u8", "CCTV-1")

    result = update_playlist.dedupe_entries([first, duplicate, alternate])

    assert result == [first, alternate]


def test_write_playlist_outputs_extm3u_and_entries(tmp_path):
    entry = update_playlist.ChannelEntry(
        source="cn",
        extinf="#EXTINF:-1 tvg-id=\"CCTV1.cn\" group-title=\"China\",CCTV-1",
        attrs={"tvg-id": "CCTV1.cn", "group-title": "China"},
        name="CCTV-1",
        url="https://example.com/cctv1.m3u8",
    )
    output = tmp_path / "live.m3u"

    update_playlist.write_playlist(output, [entry])

    assert output.read_text(encoding="utf-8") == (
        "#EXTM3U\n"
        '#EXTINF:-1 tvg-id="CCTV1.cn" group-title="China",CCTV-1\n'
        "https://example.com/cctv1.m3u8\n"
    )


class FakeResponse:
    def __init__(self, status_code=200, text="#EXTM3U\n#EXT-X-TARGETDURATION:10\n", headers=None):
        self.status_code = status_code
        self._text = text
        self.headers = headers or {"content-type": "application/vnd.apple.mpegurl"}

    @property
    def text(self):
        return self._text

    def iter_content(self, chunk_size=8192, decode_unicode=True):
        del chunk_size, decode_unicode
        yield self._text


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse()
        self.error = error
        self.calls = []

    def get(self, url, timeout, headers, stream):
        self.calls.append({"url": url, "timeout": timeout, "headers": headers, "stream": stream})
        if self.error:
            raise self.error
        return self.response


def test_probe_entry_accepts_valid_hls_playlist():
    session = FakeSession(FakeResponse(text="#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nchild.m3u8\n"))

    result = update_playlist.probe_entry(make_entry("https://example.com/live.m3u8"), session=session, timeout=3)

    assert result.ok is True
    assert result.reason == "ok"
    assert session.calls[0]["timeout"] == 3
    assert session.calls[0]["stream"] is True
    assert "Mozilla" in session.calls[0]["headers"]["User-Agent"]


def test_probe_entry_rejects_http_error():
    session = FakeSession(FakeResponse(status_code=404, text="not found"))

    result = update_playlist.probe_entry(make_entry("https://example.com/missing.m3u8"), session=session, timeout=3)

    assert result.ok is False
    assert result.reason == "http_404"


def test_probe_entry_rejects_invalid_hls_text():
    session = FakeSession(FakeResponse(text="plain text", headers={"content-type": "text/plain"}))

    result = update_playlist.probe_entry(make_entry("https://example.com/live.m3u8"), session=session, timeout=3)

    assert result.ok is False
    assert result.reason == "invalid_hls"


def test_probe_entry_accepts_stream_like_non_m3u8_response():
    session = FakeSession(FakeResponse(text="", headers={"content-type": "video/mp2t"}))

    result = update_playlist.probe_entry(make_entry("https://example.com/live.ts"), session=session, timeout=3)

    assert result.ok is True
    assert result.reason == "ok"


def test_write_report_outputs_consistent_counts(tmp_path):
    passed = [make_entry("https://example.com/pass.m3u8", "Pass")]
    failed = [update_playlist.ProbeResult(make_entry("https://example.com/fail.m3u8", "Fail"), False, "timeout")]
    skipped = [(make_entry("udp://239.1.1.1:1234", "Skip"), "unsupported_protocol")]
    source_errors = {"hk": "HTTP 500"}
    output = tmp_path / "report.json"

    update_playlist.write_report(
        output,
        sources=["cn", "hk"],
        total_channels=3,
        passed=passed,
        failed=failed,
        skipped=skipped,
        source_errors=source_errors,
        generated_at="2026-06-29T22:10:00Z",
    )

    data = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert data["generated_at"] == "2026-06-29T22:10:00Z"
    assert data["sources"] == ["cn", "hk"]
    assert data["total_channels"] == 3
    assert data["passed"] == 1
    assert data["failed"] == 1
    assert data["skipped"] == 1
    assert data["source_errors"] == {"hk": "HTTP 500"}
    assert data["failures"][0]["name"] == "Fail"
    assert data["failures"][0]["reason"] == "timeout"
    assert data["skips"][0]["reason"] == "unsupported_protocol"


def test_generate_outputs_returns_nonzero_when_no_channels_pass(tmp_path):
    def fake_fetch(source):
        return "#EXTM3U\n#EXTINF:-1,Only UDP\nudp://239.1.1.1:1234\n"

    exit_code = update_playlist.generate_outputs(
        output_dir=tmp_path,
        sources=["cn"],
        fetch_playlist=fake_fetch,
        probe=lambda entry: update_playlist.ProbeResult(entry, False, "not_called"),
        generated_at="2026-06-29T22:10:00Z",
    )

    assert exit_code == 1
    assert (tmp_path / "report.json").exists()
    assert not (tmp_path / "live.m3u").exists()


def test_generate_outputs_writes_playlist_and_report_for_passing_channel(tmp_path):
    def fake_fetch(source):
        return "#EXTM3U\n#EXTINF:-1 group-title=\"China\",CCTV-1\nhttps://example.com/cctv1.m3u8\n"

    exit_code = update_playlist.generate_outputs(
        output_dir=tmp_path,
        sources=["cn"],
        fetch_playlist=fake_fetch,
        probe=lambda entry: update_playlist.ProbeResult(entry, True, "ok"),
        generated_at="2026-06-29T22:10:00Z",
    )

    assert exit_code == 0
    assert "CCTV-1" in (tmp_path / "live.m3u").read_text(encoding="utf-8")
    report = __import__("json").loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["passed"] == 1
    assert report["failed"] == 0
    assert report["skipped"] == 0


def test_probe_entries_preserves_input_order():
    entries = [
        make_entry("https://example.com/one.m3u8", "One"),
        make_entry("https://example.com/two.m3u8", "Two"),
        make_entry("https://example.com/three.m3u8", "Three"),
    ]

    results = update_playlist.probe_entries(entries, timeout=3, workers=2)

    assert [result.entry.name for result in results] == ["One", "Two", "Three"]
