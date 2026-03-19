"""
generate.py — Genererar roliga fotbollsnyheter med Claude och pushar till GitHub.

Användning:
  python generate.py                  # Generera 3 nya artiklar
  python generate.py --antal 5        # Generera 5 artiklar
  python generate.py --tema "VM 2026" # Specifikt tema

Kräver miljövariabler (lägg i .env eller sätt i terminalen):
  ANTHROPIC_API_KEY   — din Claude API-nyckel
  GITHUB_TOKEN        — GitHub Personal Access Token (repo-rättigheter)
  GITHUB_REPO         — t.ex. "dittnamn/fotbollsnyheter"
"""

import anthropic
import json
import base64
import urllib.request
import urllib.error
import os
import sys
import argparse
from datetime import date

# ── Konfiguration ────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN      = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO       = os.environ.get("GITHUB_REPO", "")   # "användare/repo"
CONTENT_FILE      = "content.json"                        # sökväg i repot

# ── Innehållsgenerering ──────────────────────────────────────────────────────

def generera_nyheter(antal: int = 3, tema: str = "") -> dict:
    """Anropar Claude för att generera roliga fotbollsnyheter som JSON."""

    tema_text = f'Fokusera gärna på temat: "{tema}".' if tema else ""

    prompt = f"""Du är en rolig och kreativ sportjournalist som skriver underhållande, 
humoristiska fotbollsnyheter. Hitta på {antal} korta, roliga nyhetsartiklar.

{tema_text}

Svara ENDAST med ett JSON-objekt i detta exakta format (inga backticks, ingen förklarande text):

{{
  "title": "Roliga Fotbollsnyheter",
  "subtitle": "En mening som beskriver veckans nyheter på ett roligt sätt",
  "updated": "{date.today().isoformat()}",
  "articles": [
    {{
      "id": 1,
      "emoji": "ett passande emoji",
      "headline": "Rolig rubrik, max 10 ord",
      "summary": "2-3 meningar som berättar den roliga historien. Ska vara underhållande och lätt överdrivet.",
      "tag": "Kort kategori, max 3 ord"
    }}
  ]
}}

Var kreativ, hitta på absurda men trovärdiga situationer. Blanda gärna riktiga fotbollsbegrepp 
med oväntade händelser (djur, misstag, konstiga regler, roliga statistik osv).
Skriv på svenska."""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    # Rensa bort eventuella markdown-backticks
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ── GitHub-publicering ───────────────────────────────────────────────────────

def hämta_nuvarande_sha() -> str | None:
    """Hämtar SHA för nuvarande content.json (krävs vid uppdatering)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONTENT_FILE}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # Filen finns inte än
        raise


def pusha_till_github(innehåll: dict) -> bool:
    """Uppdaterar content.json i GitHub-repot via API."""
    sha = hämta_nuvarande_sha()

    json_bytes = json.dumps(innehåll, ensure_ascii=False, indent=2).encode("utf-8")
    encoded = base64.b64encode(json_bytes).decode("utf-8")

    payload = {
        "message": f"Uppdaterar innehåll {date.today().isoformat()}",
        "content": encoded,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONTENT_FILE}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json"
    })

    with urllib.request.urlopen(req) as resp:
        status = resp.status
        return status in (200, 201)


# ── Huvud ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generera fotbollsnyheter med Claude")
    parser.add_argument("--antal", type=int, default=3, help="Antal artiklar (standard: 3)")
    parser.add_argument("--tema",  type=str, default="",  help="Valfritt tema för nyheterna")
    args = parser.parse_args()

    # Kontrollera konfiguration
    saknas = [k for k, v in {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "GITHUB_TOKEN":      GITHUB_TOKEN,
        "GITHUB_REPO":       GITHUB_REPO
    }.items() if not v]

    if saknas:
        print(f"❌ Saknade miljövariabler: {', '.join(saknas)}")
        print("   Sätt dem i terminalen eller i en .env-fil.")
        sys.exit(1)

    print(f"🤖 Genererar {args.antal} fotbollsnyheter med Claude...")
    if args.tema:
        print(f"   Tema: {args.tema}")

    innehåll = generera_nyheter(args.antal, args.tema)
    print(f"✅ Genererade {len(innehåll['articles'])} artiklar")
    print(f"   Subtitle: {innehåll['subtitle']}")

    print(f"\n📤 Pushar till GitHub ({GITHUB_REPO})...")
    ok = pusha_till_github(innehåll)

    if ok:
        print("✅ Klart! Netlify deployar automatiskt inom ~30 sekunder.")
        print(f"   Innehåll uppdaterat: {innehåll['updated']}")
    else:
        print("❌ Något gick fel vid push till GitHub.")
        sys.exit(1)


if __name__ == "__main__":
    main()
