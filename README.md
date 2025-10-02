#  KI-gestützter Discord Wissensbot

Ein intelligenter Discord-Bot, der als persönliche Wissensdatenbank fungiert. Der Bot sammelt automatisch Nachrichten aus Discord-Channels und ermöglicht KI-gestützte Suche und Anfragen mit Google Gemini AI.

##  Features

### Phase 1: Grundfunktionen 
- **Automatische Nachrichtensammlung**: Sammelt alle Nachrichten aus Discord-Channels
- **Persistente Speicherung**: Nachrichten werden in `gesammelte_nachrichten.json` gespeichert
- **Basis-Befehle**: `/hallo`, `/stats`, `/reset`

### Phase 2: KI-Integration 
- ** Intelligente Suche** (`/suche`): KI-gestützte Suche mit Zusammenfassungen
- ** Natürlichsprachige Anfragen** (`/frage`): Stelle Fragen zu deinen Nachrichten
- **Google Gemini AI**: Kontextbewusste Antworten basierend auf gesammelten Daten

### Phase 3: Erweiterte Features (geplant)
- Web-Interface für erweiterte Suche
- Datenbank-Anbindung für bessere Performance
- Erweiterte Analyse-Tools

##  Installation & Setup

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
1. Gehe zu [Discord Developer Portal](https://discord.com/developers/applications)
2. Erstelle eine neue Application
3. Gehe zu "Bot" → "Token" → "Copy"

#### Google Gemini API Key:
1. Gehe zu [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Erstelle einen neuen API-Key
3. Kopiere den Key in deine `.env` Datei

> ** Kostenlose Gemini API:** Der Bot ist für die kostenlose Gemini API optimiert!
> - **Rate Limit:** 15 Anfragen pro Minute
> - **Automatisches Rate Limiting:** 4 Sekunden Wartezeit zwischen API-Aufrufen
> - **Intelligente Fehlerbehandlung:** Benutzerfreundliche Meldungen bei Limits

### 4. Bot starten
```bash
python bot.py
```

##  Verfügbare Befehle

| Befehl | Beschreibung |
|--------|-------------|
| `/hallo` | Begrüßung und Status des Bots |
| `/suche [begriff]` | KI-gestützte Suche in gesammelten Nachrichten |
| `/frage [frage]` | Stelle natürlichsprachige Fragen zu deinen Daten |
| `/stats` | Zeigt Statistiken über gesammelte Nachrichten |
| `/reset` | Löscht alle Daten (nur für Admins) |

## 🔧 Konfiguration

### Bot-Berechtigungen
Der Bot benötigt folgende Discord-Berechtigungen:
- `Read Messages`
- `Send Messages` 
- `Use Slash Commands`
- `Read Message History`

### Privileged Gateway Intents
Aktiviere im Discord Developer Portal:
-  `Message Content Intent`

##  Datenstruktur

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

## KI-Features

### Optimiert für kostenlose Gemini API
- **Neuestes Modell**: Verwendet `gemini-2.5-flash-lite` für schnellste und kosteneffizienteste Antworten
- **Rate Limiting**: Automatische 3-Sekunden-Wartezeit zwischen API-Aufrufen
- **Intelligente Fehlerbehandlung**: Spezifische Meldungen für Quota-, Raten- und API-Schlüssel-Probleme
- **Effiziente Prompts**: Optimierte Anfragen für bessere Performance bei kostenlosen Limits
- **Fallback-Mechanismen**: Graceful Degradation bei API-Problemen

## Discord Bot Best Practices

### Moderne Discord.py Implementation
- **Slash Commands**: Vollständig auf moderne Slash-Befehle umgestellt
- **Automatische Synchronisierung**: Commands werden beim Start automatisch mit Discord synchronisiert
- **Rich Embeds**: Alle Antworten verwenden ansprechende Discord-Embeds
- **Proper Error Handling**: Umfassende Fehlerbehandlung für alle Interaktionen
- **Deferred Responses**: Sofortige Antworten bei längeren Verarbeitungszeiten
- **Permission Checks**: Admin-Befehle mit korrekter Berechtigungsprüfung
- **Performance Optimierung**: Nachrichtenlimit und effiziente Datenstrukturen

## Sicherheit

- API-Keys werden über Umgebungsvariablen verwaltet
- Keine Hardcoding von Tokens im Code
- `.env` Datei ist in `.gitignore` ausgeschlossen

##  Entwicklung

### Projektstruktur
```
meinkibot/
├── bot.py                    # Hauptbot-Code
├── requirements.txt          # Python-Abhängigkeiten
├── .env.example             # Umgebungsvariablen-Template
├── .env                     # Deine API-Keys (nicht in Git)
├── gesammelte_nachrichten.json  # Gespeicherte Nachrichten
└── README.md                # Diese Dokumentation
```

### Nächste Schritte
- [ ] Web-Interface implementieren
- [ ] Datenbank-Integration (PostgreSQL/MongoDB)
- [ ] Erweiterte Suchfilter
- [ ] Export-Funktionen
- [ ] Backup-System

## Dateien

- `bot.py` - Hauptcode des Bots
- `requirements.txt` - Python-Abhängigkeiten
- `gesammelte_nachrichten.json` - Gespeicherte Nachrichten (wird automatisch erstellt)

##  Sicherheitshinweise

- **Niemals** deinen Bot-Token öffentlich teilen
- Bewahre den Token sicher auf
- Verwende Umgebungsvariablen für den Token in Produktionsumgebungen

## Nächste Schritte (Erweiterungen)

- SQLite-Datenbank statt JSON-Datei
- OpenAI API Integration für intelligentere Antworten
- Web-Interface mit Flask
- Erweiterte Suchfunktionen (Regex, Datum, Autor)
- Backup-Funktionen

## 📞 Support

Bei Problemen oder Fragen kannst du:
1. Die Konsole auf Fehlermeldungen überprüfen
2. Den `/stats` Befehl verwenden um zu sehen ob Nachrichten gesammelt werden
3. Sicherstellen, dass der Bot die nötigen Berechtigungen hat
