# Setup

This starter deliberately keeps the visible `README.md` banner-only.

## 1. Make it your profile README

GitHub renders a profile README only from a **public repository named exactly `Mitanshp5`** under the `Mitanshp5` account.

```bash
git clone https://github.com/FRIDAY-Hermes-Coder/miles-readme-starter.git
cd miles-readme-starter
git remote set-url origin https://github.com/Mitanshp5/Mitanshp5.git
git push -u origin main
```

Create `Mitanshp5/Mitanshp5` as a new, empty public repository first. If you want to keep this starter repository too, clone it before changing the remote.

## 2. Enable actual Spotify Now Playing

Without Spotify secrets, the image always renders the **Sunflower** fallback with the official album cover. With secrets, it shows your current Spotify track and its album cover only while Spotify reports active playback; otherwise it returns to Sunflower.

1. Create a Spotify app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Obtain an OAuth refresh token with the `user-read-currently-playing` scope. The upstream reference project describes a local authorization flow, but do not commit credentials or tokens.
3. In your GitHub profile repository: **Settings → Secrets and variables → Actions**, add:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_REFRESH_TOKEN`
4. Go to **Actions → Update Spotify banner → Run workflow** once.

The workflow then attempts a refresh every 15 minutes. GitHub scheduling is not real-time and can be delayed, so the visual is a snapshot rather than a live player.

## Design notes

- `assets/miles-hero.png` is the image supplied for this README. Replace it only with artwork you are allowed to publish.
- `scripts/generate_banner.py` produces the one-piece `assets/banner.svg` used by the profile. It has no runtime dependencies.
- Current playback shows its track details and a red music-bar signal; fallback shows Sunflower in the same card.
