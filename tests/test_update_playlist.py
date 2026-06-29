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
