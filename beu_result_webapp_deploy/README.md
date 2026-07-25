# BEU Result Console

Flask web app for scraping BEU result records by college code, year, and branch code.

## Run locally

```bash
python -m venv myenv
./myenv/bin/pip install -r requirements.txt
./myenv/bin/python app.py
```

Open `http://127.0.0.1:5000`.

## Deploy free

This app is not a static website. It needs a Python server plus Google Chrome for Selenium, so deploy it as a Docker web service.

### Option 1: Render

Render currently supports free Python web services, and this folder includes `render.yaml`.

1. Create a GitHub repository.
2. Upload only this folder's files to the repository root.
3. Go to Render and create a new Blueprint or Web Service from that repo.
4. Select Docker runtime if asked.
5. Keep the free plan.
6. Deploy.

### Option 2: Koyeb

Koyeb currently offers one free web service per organization with limited resources.

1. Create a GitHub repository.
2. Upload only this folder's files to the repository root.
3. Create a Koyeb Web Service from GitHub.
4. Choose Dockerfile deployment.
5. Set environment variable `HEADLESS=1`.
6. Deploy on the free instance.

## Important limit

Selenium + Chrome can be heavy for free hosting. If the deploy starts but scraping fails, the host may not have enough CPU/RAM or may block automated browser traffic. The app will still work best on your local machine or a small paid VPS.
# Results-
# Results-
