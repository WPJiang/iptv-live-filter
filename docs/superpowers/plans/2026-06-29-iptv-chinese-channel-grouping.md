# IPTV Chinese Channel Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `iptv-live-filter` so generated Televizo playlists use Chinese `group-title` values, grouped by region first and content category where appropriate.

**Architecture:** Add a pure `classify_group(entry)` function to `scripts/update_playlist.py` and have `format_extinf(entry)` replace iptv-org's original English `group-title` with the computed Chinese group. Keep the rest of the existing generation, filtering, probing, reporting, and GitHub Pages workflow unchanged.

**Tech Stack:** Python 3.11, pytest, requests, GitHub Actions, GitHub Pages.

---

## File Structure

Modify existing project files under `D:/jiangweipeng/VPN搭建/iptv-live-filter/`:

- `scripts/update_playlist.py` — add Chinese grouping constants and classifier; update `format_extinf` to output classified Chinese `group-title`.
- `tests/test_update_playlist.py` — add classifier tests and update existing `format_extinf` expectation from English to Chinese grouping.
- `README.md` — document Chinese grouping behavior and limitations.
- `public/live.m3u` — regenerate with Chinese `group-title` values.
- `public/report.json` — regenerate alongside `live.m3u`.

No new runtime dependencies are required.

---

### Task 1: Add Chinese Group Classifier

**Files:**
- Modify: `tests/test_update_playlist.py`
- Modify: `scripts/update_playlist.py`

- [ ] **Step 1: Add failing classifier tests**

Append these tests after `make_entry()` in `tests/test_update_playlist.py`:

```python

def make_entry_with_attrs(source: str, name: str, attrs: dict[str, str] | None = None) -> update_playlist.ChannelEntry:
    attrs = attrs or {}
    return update_playlist.ChannelEntry(
        source=source,
        extinf=f"#EXTINF:-1,{name}",
        attrs=attrs,
        name=name,
        url="https://example.com/live.m3u8",
    )


def test_classify_group_mainland_central_tv():
    assert update_playlist.classify_group(make_entry_with_attrs("cn", "CCTV-1 (1080p)")) == "内地｜中央电视台"
    assert update_playlist.classify_group(make_entry_with_attrs("cn", "CGTN Documentary")) == "内地｜中央电视台"
    assert update_playlist.classify_group(make_entry_with_attrs("cn", "CETV1")) == "内地｜中央电视台"


def test_classify_group_mainland_provincial_satellite_tv():
    assert update_playlist.classify_group(make_entry_with_attrs("cn", "Hunan TV")) == "内地｜省级卫视"
    assert update_playlist.classify_group(make_entry_with_attrs("cn", "Shenzhen Satellite TV")) == "内地｜省级卫视"
    assert update_playlist.classify_group(make_entry_with_attrs("cn", "BRTV 北京卫视")) == "内地｜省级卫视"


def test_classify_group_mainland_local_channels():
    assert update_playlist.classify_group(make_entry_with_attrs("cn", "Harbin Movie Channel")) == "内地｜地方频道"
    assert update_playlist.classify_group(make_entry_with_attrs("cn", "Guangzhou TV")) == "内地｜地方频道"
    assert update_playlist.classify_group(make_entry_with_attrs("cn", "Unknown Mainland Channel")) == "内地｜地方频道"


def test_classify_group_region_sources():
    assert update_playlist.classify_group(make_entry_with_attrs("hk", "RTHK TV 31")) == "香港"
    assert update_playlist.classify_group(make_entry_with_attrs("mo", "TDM Macau")) == "澳门"
    assert update_playlist.classify_group(make_entry_with_attrs("tw", "Taiwan News")) == "台湾"
    assert update_playlist.classify_group(make_entry_with_attrs("us", "Local US Channel")) == "美国"


def test_classify_group_content_categories():
    assert update_playlist.classify_group(make_entry_with_attrs("us", "ABN China", {"group-title": "Religious"})) == "内容｜宗教"
    assert update_playlist.classify_group(make_entry_with_attrs("us", "VOA Chinese", {"group-title": "News"})) == "内容｜新闻"
    assert update_playlist.classify_group(make_entry_with_attrs("us", "Outdoor Education", {"group-title": "Education;Outdoor"})) == "内容｜教育"
    assert update_playlist.classify_group(make_entry_with_attrs("us", "Unknown", {"group-title": "Undefined"})) == "内容｜综合"
```

- [ ] **Step 2: Run classifier tests to verify they fail**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python -m pytest tests/test_update_playlist.py::test_classify_group_mainland_central_tv tests/test_update_playlist.py::test_classify_group_mainland_provincial_satellite_tv tests/test_update_playlist.py::test_classify_group_mainland_local_channels tests/test_update_playlist.py::test_classify_group_region_sources tests/test_update_playlist.py::test_classify_group_content_categories -q
```

Expected: FAIL with `AttributeError: module 'scripts.update_playlist' has no attribute 'classify_group'`.

- [ ] **Step 3: Add classifier constants and functions**

In `scripts/update_playlist.py`, insert this code after `SOURCE_URL_TEMPLATE = "https://iptv-org.github.io/iptv/countries/{source}.m3u"`:

```python
GROUP_MAINLAND_CENTRAL = "内地｜中央电视台"
GROUP_MAINLAND_PROVINCIAL = "内地｜省级卫视"
GROUP_MAINLAND_LOCAL = "内地｜地方频道"
GROUP_HONG_KONG = "香港"
GROUP_MACAU = "澳门"
GROUP_TAIWAN = "台湾"
GROUP_UNITED_STATES = "美国"
GROUP_CONTENT_GENERAL = "内容｜综合"

CENTRAL_TV_KEYWORDS = (
    "cctv",
    "cgtn",
    "cctv+",
    "cctv plus",
    "cetv",
    "china education television",
)

PROVINCIAL_KEYWORDS = (
    "beijing",
    "brtv",
    "北京",
    "shanghai",
    "上海",
    "tianjin",
    "天津",
    "chongqing",
    "重庆",
    "hebei",
    "河北",
    "shanxi",
    "山西",
    "nei monggol",
    "inner mongolia",
    "内蒙古",
    "liaoning",
    "辽宁",
    "jilin",
    "吉林",
    "heilongjiang",
    "黑龙江",
    "jiangsu",
    "江苏",
    "zhejiang",
    "浙江",
    "anhui",
    "安徽",
    "fujian",
    "福建",
    "jiangxi",
    "江西",
    "shandong",
    "山东",
    "henan",
    "河南",
    "hubei",
    "湖北",
    "hunan",
    "湖南",
    "guangdong",
    "广东",
    "guangxi",
    "广西",
    "hainan",
    "海南",
    "sichuan",
    "四川",
    "guizhou",
    "贵州",
    "yunnan",
    "云南",
    "xizang",
    "tibet",
    "西藏",
    "shaanxi",
    "陕西",
    "gansu",
    "甘肃",
    "qinghai",
    "青海",
    "ningxia",
    "宁夏",
    "xinjiang",
    "新疆",
    "shenzhen",
    "深圳",
)

PROVINCIAL_TV_MARKERS = (" tv", "satellite", "卫视")

CONTENT_GROUP_MAP = {
    "news": "内容｜新闻",
    "religious": "内容｜宗教",
    "movies": "内容｜电影",
    "sports": "内容｜体育",
    "kids": "内容｜少儿",
    "music": "内容｜音乐",
    "documentary": "内容｜纪录",
    "education": "内容｜教育",
    "business": "内容｜财经",
    "lifestyle": "内容｜生活",
    "entertainment": "内容｜娱乐",
    "culture": "内容｜文化",
    "outdoor": "内容｜户外",
    "cooking": "内容｜美食",
    "travel": "内容｜旅游",
    "general": GROUP_CONTENT_GENERAL,
    "undefined": GROUP_CONTENT_GENERAL,
}


def combined_entry_text(entry: ChannelEntry) -> str:
    return " ".join(
        sanitize_text(value).lower()
        for value in (entry.name, entry.attrs.get("tvg-id", ""))
        if value
    )


def content_group(entry: ChannelEntry) -> str | None:
    raw_group = entry.attrs.get("group-title", "")
    for part in raw_group.split(";"):
        mapped = CONTENT_GROUP_MAP.get(sanitize_text(part).lower())
        if mapped:
            return mapped
    return None


def is_central_tv(entry: ChannelEntry) -> bool:
    text = combined_entry_text(entry)
    return any(keyword in text for keyword in CENTRAL_TV_KEYWORDS)


def is_provincial_satellite_tv(entry: ChannelEntry) -> bool:
    text = combined_entry_text(entry)
    has_region = any(keyword in text for keyword in PROVINCIAL_KEYWORDS)
    has_marker = any(marker in text for marker in PROVINCIAL_TV_MARKERS)
    return has_region and has_marker


def classify_group(entry: ChannelEntry) -> str:
    if entry.source == "cn":
        if is_central_tv(entry):
            return GROUP_MAINLAND_CENTRAL
        if is_provincial_satellite_tv(entry):
            return GROUP_MAINLAND_PROVINCIAL
        return GROUP_MAINLAND_LOCAL

    if entry.source == "us":
        mapped = content_group(entry)
        if mapped:
            return mapped

    if entry.source == "hk":
        return GROUP_HONG_KONG
    if entry.source == "mo":
        return GROUP_MACAU
    if entry.source == "tw":
        return GROUP_TAIWAN
    if entry.source == "us":
        return GROUP_UNITED_STATES

    return content_group(entry) or GROUP_CONTENT_GENERAL
```

- [ ] **Step 4: Run classifier tests to verify they pass**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python -m pytest tests/test_update_playlist.py::test_classify_group_mainland_central_tv tests/test_update_playlist.py::test_classify_group_mainland_provincial_satellite_tv tests/test_update_playlist.py::test_classify_group_mainland_local_channels tests/test_update_playlist.py::test_classify_group_region_sources tests/test_update_playlist.py::test_classify_group_content_categories -q
```

Expected output includes:

```text
5 passed
```

- [ ] **Step 5: Commit classifier**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
git add scripts/update_playlist.py tests/test_update_playlist.py
git commit -m "feat: classify channels into chinese groups"
```

---

### Task 2: Use Chinese Grouping in Playlist Output

**Files:**
- Modify: `tests/test_update_playlist.py`
- Modify: `scripts/update_playlist.py`

- [ ] **Step 1: Update `format_extinf` tests to expect Chinese grouping**

In `tests/test_update_playlist.py`, replace the existing `test_format_extinf_preserves_metadata_and_sanitizes_name` with:

```python
def test_format_extinf_preserves_metadata_and_writes_chinese_group():
    entry = update_playlist.ChannelEntry(
        source="us",
        extinf="#EXTINF:-1 tvg-id=\"ABNChina.us@SD\" group-title=\"Religious\",ABN China\x00",
        attrs={"tvg-id": "ABNChina.us@SD", "group-title": "Religious"},
        name="ABN China\x00",
        url="https://example.com/abn.m3u8",
    )

    line = update_playlist.format_extinf(entry)

    assert line == '#EXTINF:-1 tvg-id="ABNChina.us@SD" group-title="内容｜宗教",ABN China'
    assert 'group-title="Religious"' not in line
```

- [ ] **Step 2: Run updated formatting test to verify it fails**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python -m pytest tests/test_update_playlist.py::test_format_extinf_preserves_metadata_and_writes_chinese_group -q
```

Expected: FAIL because `format_extinf` still preserves English `group-title`.

- [ ] **Step 3: Update `format_extinf` implementation**

In `scripts/update_playlist.py`, replace `format_extinf` with:

```python
def format_extinf(entry: ChannelEntry) -> str:
    parts = ["#EXTINF:-1"]
    for key in ("tvg-id", "tvg-name", "tvg-logo"):
        value = entry.attrs.get(key)
        if value:
            safe_value = sanitize_text(value).replace('"', "'")
            parts.append(f'{key}="{safe_value}"')
    parts.append(f'group-title="{classify_group(entry)}"')
    safe_name = sanitize_text(entry.name).replace('"', "'")
    return f'{" ".join(parts)},{safe_name}'
```

- [ ] **Step 4: Run full tests to verify pass**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python -m pytest -q
```

Expected output includes:

```text
23 passed
```

- [ ] **Step 5: Commit format change**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
git add scripts/update_playlist.py tests/test_update_playlist.py
git commit -m "feat: write chinese group titles"
```

---

### Task 3: Document Chinese Grouping

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README grouping section**

In `README.md`, insert this section after the `## Televizo Setup` section:

```markdown
## Channel Grouping

The generated `group-title` labels are rewritten in Chinese for easier browsing in Televizo.

Mainland China channels are grouped as:

- `内地｜中央电视台`
- `内地｜省级卫视`
- `内地｜地方频道`

Other regional groups include:

- `香港`
- `澳门`
- `台湾`
- `美国`

Non-regional content channels are grouped under content categories such as:

- `内容｜新闻`
- `内容｜宗教`
- `内容｜电影`
- `内容｜体育`
- `内容｜少儿`
- `内容｜综合`

The classifier is heuristic. Some channels may be misclassified when iptv-org channel names are ambiguous; keyword rules can be extended later.
```

- [ ] **Step 2: Verify README contains grouping documentation**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python - <<'PY'
from pathlib import Path
text = Path('README.md').read_text(encoding='utf-8')
for needle in ['## Channel Grouping', '内地｜中央电视台', '内地｜省级卫视', '内地｜地方频道', '内容｜宗教']:
    assert needle in text, needle
print('readme grouping ok')
PY
```

Expected output:

```text
readme grouping ok
```

- [ ] **Step 3: Commit README update**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
git add README.md
git commit -m "docs: explain chinese channel grouping"
```

---

### Task 4: Regenerate Playlist and Verify Group Titles

**Files:**
- Modify: `public/live.m3u`
- Modify: `public/report.json`

- [ ] **Step 1: Run tests before regeneration**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python -m pytest -q
```

Expected output includes:

```text
23 passed
```

- [ ] **Step 2: Regenerate playlist**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python scripts/update_playlist.py --output-dir public --sources cn,hk,mo,tw,us --timeout 8 --workers 12
```

Expected: command exits with code 0 and updates `public/live.m3u` and `public/report.json`.

- [ ] **Step 3: Verify generated playlist uses Chinese groups**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python - <<'PY'
from pathlib import Path
text = Path('public/live.m3u').read_text(encoding='utf-8')
assert text.splitlines()[0] == '#EXTM3U'
for forbidden in [
    'group-title="News"',
    'group-title="Religious"',
    'group-title="General"',
    'group-title="Movies"',
    'group-title="Undefined"',
]:
    assert forbidden not in text, forbidden
for required in [
    'group-title="内地｜中央电视台"',
    'group-title="内地｜省级卫视"',
    'group-title="内地｜地方频道"',
    'group-title="内容｜宗教"',
]:
    assert required in text, required
print('playlist grouping ok')
PY
```

Expected output:

```text
playlist grouping ok
```

- [ ] **Step 4: Inspect output summary**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python - <<'PY'
from pathlib import Path
import json
report = json.loads(Path('public/report.json').read_text(encoding='utf-8'))
print(json.dumps({
    'total_channels': report['total_channels'],
    'passed': report['passed'],
    'failed': report['failed'],
    'skipped': report['skipped'],
    'source_errors': report['source_errors'],
}, ensure_ascii=False, indent=2))
PY
```

Expected: counts print successfully and `source_errors` is `{}` or otherwise clearly explained by the report.

- [ ] **Step 5: Clean caches**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
rm -rf .pytest_cache scripts/__pycache__ tests/__pycache__ .claude
```

Expected: local generated caches are removed.

- [ ] **Step 6: Commit regenerated outputs**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
git add public/live.m3u public/report.json
git commit -m "chore: regenerate playlist with chinese groups"
```

---

### Task 5: Final Review and Push

**Files:**
- Verify repository state.

- [ ] **Step 1: Run final tests**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
python -m pytest -q
```

Expected output includes:

```text
23 passed
```

- [ ] **Step 2: Verify git status is clean**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
rm -rf .pytest_cache scripts/__pycache__ tests/__pycache__ .claude
git status --short
```

Expected: no output.

- [ ] **Step 3: Verify remote**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
git remote -v
```

Expected output includes:

```text
origin	https://github.com/WPJiang/iptv-live-filter.git (fetch)
origin	https://github.com/WPJiang/iptv-live-filter.git (push)
```

- [ ] **Step 4: Push to GitHub**

Run:

```bash
cd "D:/jiangweipeng/VPN搭建/iptv-live-filter"
git push origin main
```

Expected: push succeeds.

- [ ] **Step 5: Verify GitHub Pages URL after workflow**

After GitHub Actions finishes, open:

```text
https://wpjiang.github.io/iptv-live-filter/live.m3u
```

Expected: playlist starts with `#EXTM3U` and contains Chinese `group-title` labels.

---

## Self-Review

- Spec coverage: Tasks cover classifier function, mainland central/provincial/local rules, Hong Kong/Macau/Taiwan/US regional groups, US content-category precedence, content category Chinese mapping, semicolon category handling, format output change, README update, playlist regeneration, and verification that old English group titles are absent.
- Placeholder scan: No TBD/TODO/placeholder instructions remain.
- Type consistency: The plan consistently uses `ChannelEntry`, `classify_group(entry)`, `content_group(entry)`, `format_extinf(entry)`, and existing test helpers.
