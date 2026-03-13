# AnimeCaos Mobile

This folder contains the new mobile architecture:

- `backend/`: Python FastAPI service that reuses the current AnimeCaos scraping core (Selenium plugins).
- `android/`: Android app (Kotlin + Jetpack Compose) that consumes the backend API.

## Architecture

1. Android app sends requests (`search`, `episodes`, `player-url`) to the backend.
2. Backend uses existing `animecaos.services.anime_service` and plugin system.
3. Backend resolves stream URLs and returns them to the app.
4. Android app can play using Android-native player stack (next step: Media3/ExoPlayer integration).

## Backend run (local)

```bash
cd mobile/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

By default, mobile backend queries three plugins:
`animesonlinecc,animefire,animesvision`.

You can override plugin selection with:
`ANIMECAOS_PLUGINS=animesonlinecc,animefire,animesvision`

`ANIMECAOS_DEBUG` is now only for debug/runtime behavior and no longer limits plugin count.

## Android run (local)

1. Open `mobile/android` in Android Studio.
2. Sync Gradle.
3. Run on emulator/device.

### API Base URL Configuration

**Default:** `http://10.0.0.4:8000/` (VPS production server)

The app will try URLs in this order:
1. `http://10.0.0.4:8000/` (VPS production)
2. `http://10.0.2.2:8000/` (Android emulator -> host)
3. `http://10.0.3.2:8000/` (Genymotion emulator)
4. `http://127.0.0.1:8000/` (localhost)
5. `http://localhost:8000/` (localhost)

**For local development** (backend running on your machine):

Option A: Build with custom URL:
```bash
cd mobile/android
./gradlew assembleDebug -PapiBaseUrl=http://192.168.1.100:8000/
```

Option B: Create `local.properties` in `mobile/android/`:
```properties
apiBaseUrl=http://192.168.1.100:8000/
```

**For VPS production:**
- Backend runs on VPS at `http://10.0.0.4:8000/`
- App connects directly to VPS IP
- No configuration needed (default)

Also ensure firewall allows inbound TCP `8000` on the backend server.

## Important notes

- Selenium, Firefox and geckodriver are required in backend environment.
- This is an MVP scaffold to start integration quickly.
- Next milestone: add playback endpoint contract + Media3 player screen.
