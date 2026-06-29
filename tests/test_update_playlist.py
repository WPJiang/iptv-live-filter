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
