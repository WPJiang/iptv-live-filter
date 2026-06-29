# IPTV Live Filter

Daily refreshed, best-effort IPTV playlist for Televizo using legal public sources from [iptv-org](https://github.com/iptv-org/iptv).

The generated playlist is published through GitHub Pages:

```text
https://<github-username>.github.io/iptv-live-filter/live.m3u
```

## What This Does

- Downloads iptv-org country playlists for `cn`, `hk`, `mo`, `tw`, and `us`.
- Skips unsupported protocols such as `rtp://`, `udp://`, and `rtsp://`.
- Skips multicast addresses such as `239.x.x.x`, which require ISP IPTV networks.
- Probes HTTP/HTTPS streams with a short timeout.
- Writes a Televizo-compatible playlist to `public/live.m3u`.
- Writes diagnostics to `public/report.json`.
- Publishes `public/` to GitHub Pages every day.

## What This Does Not Do

- It does not include pirated, cracked, hotel, private, or paid IPTV sources.
- It does not bypass geo-blocks, DRM, app authentication, cookies, or paywalls.
- It does not guarantee every listed channel will play on every phone, TV, or network.

## GitHub Setup

1. Create a new public GitHub repository named `iptv-live-filter`.
2. Push these files to the repository.
3. Open the repository on GitHub.
4. Go to `Settings` → `Pages`.
5. Set `Source` to `GitHub Actions`.
6. Go to `Actions` → `Update IPTV Playlist`.
7. Click `Run workflow` once to generate the first playlist.

After the workflow succeeds, add this URL to Televizo:

```text
https://<github-username>.github.io/iptv-live-filter/live.m3u
```

Replace `<github-username>` with your GitHub username.

## Televizo Setup

1. Open Televizo.
2. Add a new M3U playlist.
3. Name it `IPTV Live Filter`.
4. Use your GitHub Pages `live.m3u` URL.
5. Save and refresh the playlist.

## Manual Local Run

Install dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run tests:

```bash
python -m pytest -q
```

Generate outputs locally:

```bash
python scripts/update_playlist.py --output-dir public --sources cn,hk,mo,tw,us --timeout 8 --workers 12
```

## Adjust Sources, Timeout, and Concurrency

Edit `.github/workflows/update.yml` and change this command:

```bash
python scripts/update_playlist.py --output-dir public --sources cn,hk,mo,tw,us --timeout 8 --workers 12
```

Examples:

```bash
python scripts/update_playlist.py --output-dir public --sources cn,hk,tw --timeout 6 --workers 8
```

```bash
python scripts/update_playlist.py --output-dir public --sources cn,hk,mo,tw,us,jp,kr --timeout 10 --workers 16
```

## Why Some Channels Still Fail

This project filters obvious failures, but public IPTV remains unstable. A channel may still fail because:

- The stream is geo-blocked.
- The stream blocks GitHub's network or your home network.
- The stream requires headers, cookies, DRM, or app authentication.
- The TV device does not support the stream codec.
- The channel is not broadcasting 24/7.
- The source disappeared after the last refresh.

## Why Multicast Sources Are Skipped

Sources such as these are ISP multicast streams:

```text
rtp://239.3.1.1:8000
udp://239.3.1.1:8000
```

They usually only work inside a specific ISP IPTV VLAN or behind a correctly configured router with IGMP/udpxy. They are not ordinary public Internet streams, so this project skips them.

## Output Files

- `public/live.m3u` — Televizo playlist.
- `public/report.json` — diagnostic report with counts and failure reasons.
