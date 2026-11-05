# AutoMoto Cloud Studio (isolated deployment branch)

This branch is an **isolated beta**; the original AI assistant project's `main` branch is unchanged.

Render build: `pip install -r automoto-requirements.txt`

Render start: `python cloud_app.py`

Required Render environment variable: `STUDIO_ACCESS_KEY` (20+ random characters). Do not commit or share your secret.

Open the deployed site over HTTPS. Browser Basic Auth username: `studio`, password: the environment variable value.

Upload a ZIP containing five original V6 BMW shots (`hero.jpg`, `headlights.jpg`, `profile.jpg`, `wheel.jpg`, `rear.jpg`). Click Generate. Download the MP4 before Render sleeps or restarts.

Limitations: Render Free storage is ephemeral and can lose uploaded images/videos; full-HD renders may exceed free RAM/CPU limits. This is photograph-based animation with original synthesized beat, not moving-vehicle AI video or verified Instagram trend ranking. Render is a separate web service from the AI assistant, with a unique service name and branch. No automatic posting, user accounts, or paid image API calls. The user retains their local V6 model as a reliable fallback.
