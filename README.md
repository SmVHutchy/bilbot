# KI-gestützter Discord Wissensbot

Ein intelligenter Discord-Bot, der als persönliche Wissensdatenbank fungiert. Der Bot sammelt automatisch Nachrichten aus Discord-Channels und ermöglicht KI-gestützte Suche und Anfragen mit Google Gemini AI.

## Features

### Phase 1: Grundfunktionen
- Automatische Nachrichtensammlung: Sammelt alle Nachrichten aus Discord-Channels
- Persistente Speicherung: Nachrichten werden in `gesammelte_nachrichten.json` gespeichert
- Basis-Befehle: `/hallo`, `/stats`

### Phase 2: KI-Integration
- Intelligente Suche (`/suche`): KI-gestützte Suche mit Zusammenfassungen
- Natürlichsprachige Anfragen (`/frage`): Stelle Fragen zu deinen Nachrichten
- Google Gemini AI: Kontextbewusste Antworten basierend auf gesammelten Daten

### Phase 3: Erweiterte Features (geplant)
- Web-Interface für erweiterte Suche
- Datenbank-Anbindung für bessere Performance
- Erweiterte Analyse-Tools

## Installation & Setup

### 1. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

### 2. Umgebungsvariablen konfigurieren
Erstelle eine `.env` Datei basierend auf `.env.example`:

```env
# Discord Bot Configuration
DISCORD_TOKEN=dein_discord_bot_token

# Google Gemini AI Configuration
GEMINI_API_KEY=dein_gemini_api_key
```

### 3. API-Keys beschaffen

#### Discord Bot Token:
1. Gehe zu https://discord.com/developers/applications
2. Erstelle eine neue Application
3. Gehe zu "Bot" → "Token" → "Copy"

#### Google Gemini API Key:
1. Gehe zu https://makersuite.google.com/app/apikey
2. Erstelle einen neuen API-Key
3. Kopiere den Key in deine `.env` Datei

Hinweis zur kostenlosen Gemini API:
- Rate Limit: 15 Anfragen pro Minute
- Automatisches Rate Limiting: 3–4 Sekunden Wartezeit zwischen API-Aufrufen
- Fehlerbehandlung: Benutzerfreundliche Meldungen bei Limits

### 4. Bot starten
```bash
python bot.py
```

## Verfügbare Befehle

| Befehl | Beschreibung |
|--------|-------------|
| `/hallo` | Begrüßung und Status des Bots |
| `/suche [begriff]` | KI-gestützte Suche in gesammelten Nachrichten |
| `/frage [frage]` | Stelle natürlichsprachige Fragen zu deinen Daten |
| `/stats` | Zeigt Statistiken über gesammelte Nachrichten |

## Konfiguration

### Bot-Berechtigungen
Der Bot benötigt folgende Discord-Berechtigungen:
- Read Messages
- Send Messages
- Use Slash Commands
- Read Message History
- Create Public Threads
- Send Messages in Threads

### Privileged Gateway Intents
Aktiviere im Discord Developer Portal:
- Message Content Intent

## Datenstruktur

Nachrichten werden in folgendem Format gespeichert:
```json
{
  "id": "nachricht_id",
  "inhalt": "Nachrichtentext",
  "autor": "Benutzername",
  "channel": "channel-name",
  "server": "Server Name",
  "datum": "2024-01-01 12:00:00",
  "link": "https://discord.com/channels/..."
}
```

## Icons (modern & professionell)

Um ein professionelles Erscheinungsbild zu erreichen, verwenden wir schwarz-weiße SVG-Icons aus einer frei nutzbaren Icon-Bibliothek. Empfehlungen:
- Tabler Icons (SVG, monochrom, flexibel)
- Bootstrap Icons (SVG)
- Lucide Icons (SVG)

Verwendung in Embeds:
- Thumbnail/Author-Icon: Monochrome SVG-Dateien im Repository (z. B. `assets/icons/`)
- Konsistente Farbcodierung: Textfarben aus Discord-Embed (z. B. neutraler Grauton)

Hinweis: SVG-Dateien sind skalierbar und passen zu hellen/dunklen Discord-Themes.

Standard: Lucide Icons (bereitgestellt):
- assets/icons/search.svg
- assets/icons/question.svg
- assets/icons/bar-chart.svg
- assets/icons/info.svg
- assets/icons/alert-triangle.svg

## Threads für strukturierte Kommunikation

Geplante Erweiterung: Antworten aus `/frage` automatisch in einem Thread erstellen, um die Diskussion getrennt vom Hauptkanal zu führen.

Vorgesehenes Verhalten:
- In Channel X wird ein Public Thread erstellt (Auto-Archive konfigurierbar)
- Antwort der KI im Thread posten
- Weitere Rückfragen innerhalb desselben Threads führen

Erforderliche Berechtigungen:
- Create Public Threads
- Send Messages in Threads

Konfiguration (geplant):
- `.env` Flags: `ENABLE_THREADS=true`, `THREAD_AUTO_ARCHIVE_MINUTES=1440`, `THREAD_SLOWMODE=0`

## Discord Bot Best Practices
- Slash Commands mit automatischer Synchronisierung
- Rich Embeds für Antworten
- Fehlerbehandlung für Interaktionen
- Deferred Responses für längere Aufgaben
- Permission Checks für Admin-Befehle

## Sicherheit
- API-Keys über Umgebungsvariablen verwalten
- Keine Hardcoding von Tokens im Code
- `.env` Datei in `.gitignore` ausgeschlossen

## Entwicklung

### Projektstruktur
```
meinkibot/
├── bot.py                    # Hauptbot-Code
├── requirements.txt          # Python-Abhängigkeiten
├── .env.example             # Umgebungsvariablen-Template
├── .env                     # Deine API-Keys (nicht in Git)
├── gesammelte_nachrichten.json  # Gespeicherte Nachrichten
└── README.md                # Dokumentation
```

### Nächste Schritte
- [ ] Web-Interface implementieren
- [ ] Datenbank-Integration (SQLite → optional PostgreSQL)
- [ ] Erweiterte Suchfilter
- [ ] Export-Funktionen
- [ ] Backup-System
- [ ] Threads für `/frage`-Antworten
- [ ] Monochrome SVG-Icons für Embeds

## Support
Bei Problemen oder Fragen:
1. Konsole auf Fehlermeldungen prüfen
2. `/stats` verwenden, um zu sehen, ob Nachrichten gesammelt werden
3. Sicherstellen, dass der Bot die nötigen Berechtigungen hat
