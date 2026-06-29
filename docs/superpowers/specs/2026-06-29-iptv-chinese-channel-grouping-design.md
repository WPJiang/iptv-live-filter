# IPTV Chinese Channel Grouping Design

## Goal

Update `iptv-live-filter` so generated Televizo playlists use Chinese `group-title` values instead of iptv-org's English content categories. The playlist should primarily group channels by region, with mainland China split into central, provincial satellite, and local channel groups. Non-regional content channels should move under Chinese content-category groups.

## User-facing Output

`public/live.m3u` entries should use one of these Chinese group naming patterns:

- `内地｜中央电视台`
- `内地｜省级卫视`
- `内地｜地方频道`
- `香港`
- `澳门`
- `台湾`
- `美国`
- `内容｜新闻`
- `内容｜宗教`
- `内容｜电影`
- `内容｜体育`
- `内容｜少儿`
- `内容｜音乐`
- `内容｜纪录`
- `内容｜教育`
- `内容｜财经`
- `内容｜生活`
- `内容｜娱乐`
- `内容｜文化`
- `内容｜户外`
- `内容｜美食`
- `内容｜旅游`
- `内容｜综合`

The separator is the full-width vertical bar `｜`, not ASCII `|`.

## Classification Function

Add a pure function:

```python
classify_group(entry: ChannelEntry) -> str
```

`format_extinf(entry)` should call `classify_group(entry)` and write that value as `group-title`. It should preserve other metadata where available:

- `tvg-id`
- `tvg-name`
- `tvg-logo`

It should no longer preserve the original English `group-title` in output.

## Inputs Used for Classification

The classifier uses:

- `entry.source`: `cn`, `hk`, `mo`, `tw`, `us`
- `entry.name`: display channel name
- `entry.attrs["tvg-id"]` when available
- `entry.attrs["group-title"]` when available

Classification should be deterministic and require no external network calls or extra dependencies.

## Mainland China Rules

For `source == "cn"`, prefer regional TV grouping over content grouping.

### Central TV

Return:

```text
内地｜中央电视台
```

when the channel name or `tvg-id` indicates one of:

- `CCTV`
- `CGTN`
- `CCTV+`
- `CCTV Plus`
- `CETV`
- `China Education Television`

`CETV` belongs here instead of `内容｜教育`.

### Provincial Satellite TV

Return:

```text
内地｜省级卫视
```

when the channel looks like a provincial-level TV or satellite channel. The first version should use province/municipality/autonomous-region keywords combined with TV/satellite markers when practical.

Province and region keywords include:

- `Beijing`, `BRTV`, `北京`
- `Shanghai`, `上海`
- `Tianjin`, `天津`
- `Chongqing`, `重庆`
- `Hebei`, `河北`
- `Shanxi`, `山西`
- `Nei Monggol`, `Inner Mongolia`, `内蒙古`
- `Liaoning`, `辽宁`
- `Jilin`, `吉林`
- `Heilongjiang`, `黑龙江`
- `Jiangsu`, `江苏`
- `Zhejiang`, `浙江`
- `Anhui`, `安徽`
- `Fujian`, `福建`
- `Jiangxi`, `江西`
- `Shandong`, `山东`
- `Henan`, `河南`
- `Hubei`, `湖北`
- `Hunan`, `湖南`
- `Guangdong`, `广东`
- `Guangxi`, `广西`
- `Hainan`, `海南`
- `Sichuan`, `四川`
- `Guizhou`, `贵州`
- `Yunnan`, `云南`
- `Xizang`, `Tibet`, `西藏`
- `Shaanxi`, `陕西`
- `Gansu`, `甘肃`
- `Qinghai`, `青海`
- `Ningxia`, `宁夏`
- `Xinjiang`, `新疆`
- `Shenzhen`, `深圳`

TV/satellite markers include:

- `TV`
- `Satellite`
- `卫视`

Examples:

- `Hunan TV` → `内地｜省级卫视`
- `Hebei TV` → `内地｜省级卫视`
- `Shenzhen Satellite TV` → `内地｜省级卫视`
- `BRTV 北京卫视` → `内地｜省级卫视`

### Local Channels

Return:

```text
内地｜地方频道
```

for mainland entries that are not central or provincial satellite TV, including channels whose names contain local channel markers such as:

- `Channel`
- `News Channel`
- `Comprehensive`
- `Generalist`
- `City`
- `Lifestyle`
- `Movie Channel`
- `Rural`
- `Public`
- `Agriculture`

Also use this as the fallback for `source == "cn"` after central/provincial checks. This keeps mainland local stations out of generic content categories.

## Region Rules Outside Mainland

For non-mainland source playlists:

- `source == "hk"` → `香港`
- `source == "mo"` → `澳门`
- `source == "tw"` → `台湾`
- `source == "us"` → `美国`, unless the channel is clearly better handled by content grouping

For `source == "us"`, content grouping should take precedence when the original `group-title` maps to a content category such as `Religious` or `News`. This keeps Chinese-language content services like `ABN China` under `内容｜宗教` instead of the broad `美国` group.

## Content Category Mapping

If a channel is not classified as mainland central/provincial/local or a non-mainland regional group, map original iptv-org content categories to Chinese groups:

| Original category | Chinese group |
|---|---|
| `News` | `内容｜新闻` |
| `Religious` | `内容｜宗教` |
| `Movies` | `内容｜电影` |
| `Sports` | `内容｜体育` |
| `Kids` | `内容｜少儿` |
| `Music` | `内容｜音乐` |
| `Documentary` | `内容｜纪录` |
| `Education` | `内容｜教育` |
| `Business` | `内容｜财经` |
| `Lifestyle` | `内容｜生活` |
| `Entertainment` | `内容｜娱乐` |
| `Culture` | `内容｜文化` |
| `Outdoor` | `内容｜户外` |
| `Cooking` | `内容｜美食` |
| `Travel` | `内容｜旅游` |
| `General` | `内容｜综合` |
| `Undefined` | `内容｜综合` |

If the original group contains multiple values separated by semicolons, such as `Education;Outdoor`, use the first category that has a mapping. Example:

```text
Education;Outdoor → 内容｜教育
```

Unknown categories fall back to:

```text
内容｜综合
```

## Priority Order

The classifier should apply rules in this order:

1. `source == "cn"` central TV → `内地｜中央电视台`
2. `source == "cn"` provincial satellite TV → `内地｜省级卫视`
3. `source == "cn"` fallback/local → `内地｜地方频道`
4. `source == "us"` content category mapping if available → `内容｜...`
5. `source == "hk"` → `香港`
6. `source == "mo"` → `澳门`
7. `source == "tw"` → `台湾`
8. `source == "us"` → `美国`
9. content category mapping → `内容｜...`
10. fallback → `内容｜综合`

This priority intentionally keeps all mainland `cn` entries in mainland TV groups, even if their original iptv-org group was `News`, `Movies`, or similar.

## Testing Requirements

Add unit tests for at least these cases:

- `CCTV-1` → `内地｜中央电视台`
- `CGTN` → `内地｜中央电视台`
- `CETV1` → `内地｜中央电视台`
- `Hunan TV` → `内地｜省级卫视`
- `Shenzhen Satellite TV` → `内地｜省级卫视`
- `Harbin Movie Channel` → `内地｜地方频道`
- `Guangzhou TV` → `内地｜地方频道`
- `source=hk` → `香港`
- `source=mo` → `澳门`
- `source=tw` → `台湾`
- `source=us` with no mapped content category → `美国`
- `Religious` → `内容｜宗教`
- `News` → `内容｜新闻`
- `Education;Outdoor` → `内容｜教育`
- `Undefined` → `内容｜综合`
- `format_extinf` writes Chinese `group-title` and does not preserve English group labels.

After regenerating `public/live.m3u`, verify it does not contain English group titles such as:

- `group-title="News"`
- `group-title="Religious"`
- `group-title="General"`
- `group-title="Movies"`
- `group-title="Undefined"`

## README Update

Add a section explaining channel grouping:

- All output `group-title` labels are Chinese.
- Mainland channels are grouped as central TV, provincial satellite TV, and local channels.
- Hong Kong, Macau, Taiwan, and the United States have regional groups.
- Non-regional content channels use content groups such as `内容｜新闻` and `内容｜宗教`.
- Some channels may still be misclassified when iptv-org names are ambiguous; keyword rules can be extended later.

## Limitations

The classifier is heuristic. It should improve Televizo browsing substantially, but it will not perfectly classify every channel name in iptv-org. Future improvements can add more keywords or a small manual override table for known misclassified channels.
