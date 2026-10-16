name: Nachtfragment Stuff & Magazine Auto Update

on:
  schedule:
    - cron: "17 5 * * 0"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: nachtfragment-stuff-magazine-update
  cancel-in-progress: false

jobs:
  update-directories:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Repository auschecken
        uses: actions/checkout@v4

      - name: Python einrichten
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Abhängigkeiten installieren
        run: python -m pip install --upgrade pip requests beautifulsoup4

      - name: Stuff und Magazine aktualisieren
        env:
          SERPAPI_KEY: ${{ secrets.SERPAPI_KEY }}
        run: python stuff_magazine_updater.py

      - name: Änderungen veröffentlichen
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add Stuff/nachtfragment-stuff.json Magazine/nachtfragment-magazine.json data/stuff-magazine-review.json
          if git diff --cached --quiet; then
            echo "Keine Änderungen zu veröffentlichen."
          else
            git commit -m "chore: update Stuff and Magazine directories"
            git push
          fi
