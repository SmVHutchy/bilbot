# BilBot - Intelligente Discord-Nachrichtenverwaltung

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95.0-green)
![Discord.py](https://img.shields.io/badge/Discord.py-2.0%2B-7289DA)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)
![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen)

## 📋 Projektübersicht

BilBot ist eine moderne, skalierbare Lösung zur intelligenten Verwaltung von Discord-Nachrichten mit KI-Integration. Das Projekt kombiniert einen leistungsstarken Discord-Bot mit einer RESTful API, um Nachrichten zu sammeln, zu analysieren und intelligent darauf zu reagieren.

### 🔑 Hauptfunktionen

- **Nachrichtenverwaltung**: Automatisches Sammeln und Speichern von Discord-Nachrichten
- **KI-Integration**: Intelligente Antworten mit Google Gemini API
- **RESTful API**: Vollständige FastAPI-basierte Schnittstelle für Datenzugriff
- **Containerisierung**: Docker-Unterstützung für einfache Bereitstellung
- **Testabdeckung**: Umfassende Tests für alle Komponenten

## 🏗️ Architektur

Das Projekt folgt einer modernen, modularen Architektur:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Discord    │     │  FastAPI    │     │  Datenbank  │
│  Bot        │────▶│  Service    │────▶│  (JSON/DB)  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   ▲
       │                   │                   │
       └───────────────────┴───────────────────┘
```

## 📁 Projektstruktur

```
bilbot/
├── api/                      # FastAPI-Anwendung
│   ├── __init__.py
│   └── app.py                # Hauptanwendung mit API-Endpunkten
├── assets/                   # Statische Assets
│   └── icons/                # SVG-Icons für Bot-Antworten
├── tests/                    # Testverzeichnis
│   ├── api/                  # API-Tests
│   │   ├── test_customers.py # Tests für Kunden-Endpunkte
│   │   ├── test_invoices.py  # Tests für Rechnungs-Endpunkte
│   │   └── test_messages.py  # Tests für Nachrichten-Endpunkte
│   ├── conftest.py           # Pytest-Konfiguration
│   └── test_utils.py         # Test-Hilfsfunktionen
├── .env.example              # Beispiel für Umgebungsvariablen
├── .gitignore                # Git-Ignorierungsmuster
├── .pre-commit-config.yaml   # Pre-Commit-Hooks für Code-Qualität
├── bot.py                    # Discord-Bot-Implementierung
├── docker-compose.yml        # Docker-Compose-Konfiguration
├── Dockerfile.api            # Docker-Konfiguration für API
├── gesammelte_nachrichten.json # Gespeicherte Discord-Nachrichten
├── README.md                 # Projektdokumentation
└── requirements.txt          # Python-Abhängigkeiten
```

### 🤖 Discord Bot (bot.py)

Der BilBot Discord-Bot bietet:
- Sammeln und Speichern von Discord-Nachrichten
- KI-gestützte Antworten mit Google Gemini
- Thread-Erstellung für organisierte Konversationen
- Slash-Befehle für einfache Interaktion
- Suche in gespeicherten Nachrichten

### 🚀 FastAPI-Dienst (api/app.py)

Eine vollständige REST-API mit:
- Healthcheck-Endpunkt für Monitoring
- BilBot-spezifische Endpunkte für Discord-Nachrichten:
  - `GET /messages` - Alle Discord-Nachrichten abrufen (mit Paginierung)
  - `GET /messages/{message_id}` - Einzelne Nachricht nach ID abrufen
  - `GET /messages/search` - Nachrichten nach Inhalt, Kanal oder Autor durchsuchen
  - `GET /messages/stats` - Statistiken über gesammelte Nachrichten abrufen
- Automatische API-Dokumentation (Swagger UI unter `/docs`)
- Verbesserte Fehlerbehandlung mit strukturierten Antworten
- Paginierung und Filterung für effiziente Datenabfragen

## 🛠️ Technologiestack

- **Backend**: Python 3.8+
- **API-Framework**: FastAPI mit Pydantic für Datenvalidierung
- **Discord-Integration**: discord.py 2.0+
- **KI-Integration**: Google Gemini API
- **Containerisierung**: Docker & Docker Compose
- **Tests**: pytest
- **Code-Qualität**: pre-commit Hooks, Black, isort, mypy

## 🚀 Schnellstart-Anleitung

### Voraussetzungen

- Python 3.8+
- Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- Google Gemini API Key (optional für KI-Funktionen)

### Installation in 3 einfachen Schritten

1. **Projekt einrichten:**
   ```bash
   # Abhängigkeiten installieren
   pip install -r requirements.txt

   # Konfiguration erstellen (.env Datei)
   # Windows:
   copy .env.example .env
   # Linux/Mac:
   cp .env.example .env
   ```

2. **Konfiguration anpassen:**
   Öffne die `.env` Datei und trage deine Zugangsdaten ein:
   ```
   DISCORD_TOKEN=dein_discord_bot_token
   GEMINI_API_KEY=dein_gemini_api_key
   ```

3. **Starten:**
   ```bash
   # API starten
   python -m api.app

   # In einem neuen Terminal: Bot starten
   python bot.py
   ```

### Alternative: Docker-Installation

```bash
# Starten mit Docker Compose
docker-compose up
```

## 📚 API-Dokumentation

Die API ist unter http://localhost:8001 erreichbar.

### Endpunkte

#### Allgemein
- `GET /health` - Healthcheck-Endpunkt

#### BilBot-Nachrichten
- `GET /messages` - Liste aller Nachrichten (mit Paginierung)
- `POST /messages` - Neue Nachricht erstellen
- `GET /messages/{id}` - Nachrichtendetails abrufen
- `GET /messages/search` - Nachrichten durchsuchen (Parameter: q, channel, author)
- `GET /messages/stats` - Statistiken über Nachrichten abrufen

#### Demo-Endpunkte
- `GET /customers` - Liste aller Kunden
- `POST /customers` - Neuen Kunden erstellen
- `GET /customers/{id}` - Kundendetails abrufen
- `GET /invoices` - Liste aller Rechnungen
- `POST /invoices` - Neue Rechnung erstellen
- `GET /invoices/{id}` - Rechnungsdetails abrufen

Die interaktive API-Dokumentation (Swagger UI) ist unter http://localhost:8001/docs verfügbar.

## 🤖 Discord Bot Dokumentation

### Einrichtung

1. Erstelle eine `.env`-Datei mit folgenden Werten:
   ```
   DISCORD_TOKEN=dein_discord_bot_token
   GEMINI_API_KEY=dein_gemini_api_key
   ENABLE_THREADS=True
   THREAD_AUTO_ARCHIVE_MINUTES=1440
   THREAD_SLOWMODE=0
   ```

2. Starte den Bot:
   ```bash
   python bot.py
   ```

### Verfügbare Befehle

Der BilBot unterstützt folgende Slash-Befehle:

- `/ping` - Überprüft, ob der Bot online ist
- `/suche [suchbegriff]` - Durchsucht gespeicherte Nachrichten nach einem Begriff
- `/frage [frage]` - Stellt eine Frage an die KI (benötigt GEMINI_API_KEY)
- `/stats` - Zeigt Statistiken über gesammelte Nachrichten

### Automatische Funktionen

- **Nachrichtensammlung**: Der Bot sammelt automatisch Nachrichten in Kanälen, in denen er Leserechte hat
- **Thread-Erstellung**: Bei Aktivierung erstellt der Bot Threads für organisierte Konversationen
- **KI-Antworten**: Mit konfiguriertem GEMINI_API_KEY kann der Bot auf Fragen antworten

## 🧪 Tests

Das Projekt enthält umfassende Tests für alle Komponenten:

```bash
# Alle Tests ausführen
pytest

# Nur API-Tests ausführen
pytest tests/api/

# Mit Testabdeckung
pytest --cov=.
```

## 🔄 CI/CD

Das Projekt ist für kontinuierliche Integration mit GitHub Actions vorbereitet:
- Automatische Tests bei jedem Push
- Code-Qualitätsprüfungen mit pre-commit
- Docker-Image-Erstellung

## 📝 Lizenz

Dieses Projekt steht unter der MIT-Lizenz - siehe die [LICENSE](LICENSE) Datei für Details.

## 👥 Mitwirkende

- [Dein Name](https://github.com/yourusername) - Hauptentwickler
