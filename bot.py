import discord
from discord import app_commands
import os
import json
from datetime import datetime
import google.generativeai as genai
import asyncio
import time
from dotenv import load_dotenv
import re
import aiohttp
from bs4 import BeautifulSoup
import io
try:
    import cairosvg
except Exception:
    cairosvg = None

# Lade Umgebungsvariablen aus .env Datei
load_dotenv()

# Bot-Initialisierung mit den nötigen Berechtigungen
intents = discord.Intents.default()
intents.message_content = True  # Damit der Bot Nachrichteninhalte lesen darf

# Google Gemini API Konfiguration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Thread-Konfiguration aus .env
ENABLE_THREADS = os.getenv("ENABLE_THREADS", "true").lower() == "true"
try:
    THREAD_AUTO_ARCHIVE_MINUTES = int(os.getenv("THREAD_AUTO_ARCHIVE_MINUTES", "1440"))
except Exception:
    THREAD_AUTO_ARCHIVE_MINUTES = 1440
try:
    THREAD_SLOWMODE = int(os.getenv("THREAD_SLOWMODE", "0"))
except Exception:
    THREAD_SLOWMODE = 0
# Zulässige Auto-Archive-Dauern laut Discord API
_ALLOWED_ARCHIVE = {60, 1440, 4320, 10080}
if THREAD_AUTO_ARCHIVE_MINUTES not in _ALLOWED_ARCHIVE:
    THREAD_AUTO_ARCHIVE_MINUTES = 1440

KI_ENABLED = bool(GEMINI_API_KEY)
if KI_ENABLED:
    genai.configure(api_key=GEMINI_API_KEY)
    # Upgrade auf das neueste, kosteneffizienteste Modell für kostenlose API
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
else:
    model = None
    print("⚠️ Kein GEMINI_API_KEY gefunden. KI-Funktionen werden deaktiviert. Setze den Schlüssel in deiner .env-Datei.")

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Liste zum Speichern der Nachrichten (für Prototypen, später durch Datenbank ersetzen)
gesammelte_nachrichten = []
# Thread-Kontexte für kontinuierlichen Dialog in Threads
thread_contexts: dict[int, dict] = {}

# Datei zum Speichern der Nachrichten
NACHRICHTEN_DATEI = "gesammelte_nachrichten.json"

# Hilfsfunktionen für Icons (SVG -> PNG für Discord Embeds)
def load_icon_png_attachment(icon_name: str):
    # Versuche SVG -> PNG zu konvertieren, wenn cairosvg verfügbar ist
    if cairosvg is not None:
        try:
            svg_path = os.path.join("assets", "icons", f"{icon_name}.svg")
            with open(svg_path, "rb") as f:
                svg_data = f.read()
            png_bytes = cairosvg.svg2png(bytestring=svg_data)
            filename = f"{icon_name}.png"
            return discord.File(io.BytesIO(png_bytes), filename=filename)
        except Exception as e:
            print(f"⚠️ Icon konnte nicht konvertiert werden ({icon_name}): {e}")
    # PNG-Fallback: Lade vorhandene PNG-Datei aus dem Dateisystem
    try:
        png_path = os.path.join("assets", "icons", f"{icon_name}.png")
        if os.path.exists(png_path):
            with open(png_path, "rb") as f:
                png_bytes = f.read()
            filename = f"{icon_name}.png"
            return discord.File(io.BytesIO(png_bytes), filename=filename)
    except Exception as e:
        print(f"⚠️ PNG-Fallback fehlgeschlagen ({icon_name}): {e}")
    return None


def apply_embed_icon(embed: discord.Embed, icon_name: str, mode: str = "author", author_name: str | None = None):
    file = load_icon_png_attachment(icon_name)
    if file:
        if mode == "thumbnail":
            embed.set_thumbnail(url=f"attachment://{file.filename}")
        else:
            embed.set_author(name=author_name if author_name else (embed.title or "Info"), icon_url=f"attachment://{file.filename}")
    return file

# Einheitliche Fehler-Embed-Helferfunktion
async def send_error_embed(interaction: discord.Interaction, title: str, description: str):
    embed = discord.Embed(
        title=title,
        description=description,
        color=0xFF4D4F,
        timestamp=datetime.now()
    )
    icon_file = apply_embed_icon(embed, "alert-triangle", mode="author", author_name="Fehler")
    try:
        # Wenn die Interaktion bereits defered/acknowledged ist, nutze Followup
        if interaction.response.is_done() or getattr(interaction.response, "deferred", False):
            if icon_file:
                await interaction.followup.send(embed=embed, file=icon_file, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            if icon_file:
                await interaction.response.send_message(embed=embed, file=icon_file, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception:
        # Fallback: Followup versuchen
        try:
            if icon_file:
                await interaction.followup.send(embed=embed, file=icon_file, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Fehler beim Senden des Fehler-Embeds: {e}")


# Lade bereits gespeicherte Nachrichten beim Start
def lade_nachrichten():
    global gesammelte_nachrichten
    try:
        if os.path.exists(NACHRICHTEN_DATEI):
            with open(NACHRICHTEN_DATEI, 'r', encoding='utf-8') as f:
                gesammelte_nachrichten = json.load(f)
            print(f"✅ {len(gesammelte_nachrichten)} gespeicherte Nachrichten geladen.")
    except Exception as e:
        print(f"❌ Fehler beim Laden der Nachrichten: {e}")
        gesammelte_nachrichten = []

# Speichere Nachrichten in Datei
def speichere_nachrichten():
    try:
        with open(NACHRICHTEN_DATEI, 'w', encoding='utf-8') as f:
            json.dump(gesammelte_nachrichten, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Nachrichten: {e}")

# URL-Metadaten extrahieren
async def extrahiere_url_metadaten(url: str) -> dict:
    """Extrahiert Titel und Beschreibung von einer URL"""
    try:
        # Timeout und User-Agent für bessere Kompatibilität
        timeout = aiohttp.ClientTimeout(total=10)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Titel extrahieren
                    title = None
                    if soup.title:
                        title = soup.title.string.strip()

                    # Beschreibung extrahieren (Meta-Tags)
                    description = None
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    if meta_desc:
                        description = meta_desc.get('content', '').strip()

                    # Open Graph Titel und Beschreibung als Fallback
                    if not title:
                        og_title = soup.find('meta', property='og:title')
                        if og_title:
                            title = og_title.get('content', '').strip()

                    if not description:
                        og_desc = soup.find('meta', property='og:description')
                        if og_desc:
                            description = og_desc.get('content', '').strip()

                    return {
                        'title': title or 'Unbekannter Titel',
                        'description': description or 'Keine Beschreibung verfügbar',
                        'domain': url.split('/')[2] if '://' in url else url.split('/')[0]
                    }
    except Exception as e:
        print(f"Fehler beim Extrahieren der URL-Metadaten für {url}: {e}")

    # Fallback wenn Extraktion fehlschlägt
    domain = url.split('/')[2] if '://' in url else url.split('/')[0]
    return {
        'title': f'Link zu {domain}',
        'description': 'Metadaten konnten nicht geladen werden',
        'domain': domain
    }

# URLs in Text finden
def finde_relevante_kanaele(suchbegriff, nachrichten):
    """Findet Kanäle, die für den Suchbegriff relevant sein könnten"""
    kanal_scores = {}
    suchbegriff_lower = suchbegriff.lower()

    # Sammle alle verfügbaren Kanäle
    alle_kanaele = set()
    for nachricht in nachrichten:
        kanal = nachricht.get('channel', 'unbekannt')
        alle_kanaele.add(kanal)

    # Bewerte Kanäle basierend auf Relevanz
    for kanal in alle_kanaele:
        score = 0

        # Direkte Übereinstimmung mit Kanalnamen
        if suchbegriff_lower in kanal.lower():
            score += 100

        # Thematische Zuordnung basierend auf Suchbegriff
        themen_mapping = {
            'font': ['webseiten', 'design', 'figma', 'mockups'],
            'design': ['figma', 'mockups', 'webseiten', 'design'],
            'webseite': ['webseiten', 'ki-webseiten', 'figma-plugins'],
            'ki': ['ki-webseiten', 'education-vids'],
            'musik': ['ableton', 'audiotechnik'],
            'reise': ['travel', 'portugal', 'indonesien', 'campingplätze'],
            'schule': ['education-vids', 'mathe', 'bafög', 'bewerbungen'],
            'projekt': ['projektbericht', 'smarterblumentopf', 'android'],
            'spiel': ['tft-comps', 'wm2024-track']
        }

        for thema, relevante_kanaele in themen_mapping.items():
            if thema in suchbegriff_lower:
                for relevanter_kanal in relevante_kanaele:
                    if relevanter_kanal in kanal.lower():
                        score += 50

        if score > 0:
            kanal_scores[kanal] = score

    # Sortiere Kanäle nach Relevanz
    sortierte_kanaele = sorted(kanal_scores.items(), key=lambda x: x[1], reverse=True)

    # Wenn keine spezifischen Kanäle gefunden wurden, verwende alle
    if not sortierte_kanaele:
        return list(alle_kanaele)

    return [kanal for kanal, score in sortierte_kanaele]

def extrahiere_schluesselwoerter(text: str) -> list[str]:
    """Extrahiert einfache Schlüsselwörter (ohne Stopwörter) und führt leichtes Stemming durch."""
    tokens = re.findall(r"[a-zA-ZäöüÄÖÜß0-9]+", text.lower())
    stopwoerter = {
        'welche','was','kannst','kann','mir','dir','du','ich','wir','ihr','sie','ist','sind','war','waren','wurde','wurden',
        'schon','auch','und','oder','nicht','kein','keine','ohne','mit','zu','über','ueber','für','fuer','von','im','in','auf','am',
        'die','der','das','ein','eine','einer','eines','dem','den','dass','wie','wo','wann','warum','wieso','weshalb','frage','suche',
        'informationen','info','infos','ergebnisse','gefunden'
    }
    resultat = []
    for t in tokens:
        if t in stopwoerter or len(t) <= 2:
            continue
        # simples Stemming (deutsch/englisch sehr rudimentär)
        for suf in ("en", "er", "e", "s", "n"):
            if t.endswith(suf) and len(t) > len(suf) + 2:
                t = t[:-len(suf)]
                break
        resultat.append(t)
    # Duplikate entfernen, Reihenfolge beibehalten
    return list(dict.fromkeys(resultat))

async def hierarchische_suche(suchbegriff):
    """Führt eine hierarchische Suche durch: erst Kanäle finden, dann innerhalb der Kanäle suchen (Token-basiert)."""

    # 1. Finde relevante Kanäle
    relevante_kanaele = finde_relevante_kanaele(suchbegriff, gesammelte_nachrichten)

    # 2. Token-basierte Suche innerhalb der relevanten Kanäle
    kanal_ergebnisse = {}
    tokens = extrahiere_schluesselwoerter(suchbegriff)

    for kanal in relevante_kanaele[:5]:  # Limitiere auf die 5 relevantesten Kanäle
        kanal_nachrichten = []

        for nachricht in gesammelte_nachrichten:
            if nachricht.get('channel') == kanal:
                inhalt_lower = nachricht.get('inhalt', '').lower()
                score = 0
                # Treffer im Inhalt
                score += sum(1 for tok in tokens if tok in inhalt_lower)
                # Treffer in URL-Metadaten
                if nachricht.get('urls'):
                    for url_data in nachricht['urls']:
                        titel = url_data.get('title', '').lower()
                        beschr = url_data.get('description', '').lower()
                        domain = url_data.get('domain', '').lower()
                        if any(tok in titel or tok in beschr or tok in domain for tok in tokens):
                            score += 1
                            break
                if score > 0:
                    kanal_nachrichten.append(nachricht)

        if kanal_nachrichten:
            kanal_ergebnisse[kanal] = kanal_nachrichten

    # 3. Wenn keine kanalspezifischen Ergebnisse, führe globale token-basierte Suche durch
    if not kanal_ergebnisse:
        alle_ergebnisse = []
        for nachricht in gesammelte_nachrichten:
            inhalt_lower = nachricht.get('inhalt', '').lower()
            score = 0
            score += sum(1 for tok in tokens if tok in inhalt_lower)
            if score == 0 and nachricht.get('urls'):
                for url_data in nachricht['urls']:
                    titel = url_data.get('title', '').lower()
                    beschr = url_data.get('description', '').lower()
                    domain = url_data.get('domain', '').lower()
                    if any(tok in titel or tok in beschr or tok in domain for tok in tokens):
                        score += 1
                        break
            if score > 0:
                alle_ergebnisse.append(nachricht)

        if alle_ergebnisse:
            return await ki_suche(suchbegriff, alle_ergebnisse[:10])
        else:
            return f"🔍 Keine Ergebnisse für '{suchbegriff}' gefunden."

    # 4. Erstelle KI-gestützte Zusammenfassung pro Kanal
    ergebnis_text = f"🔍 **Hierarchische Suchergebnisse für '{suchbegriff}':**\n\n"

    for kanal, nachrichten in kanal_ergebnisse.items():
        ergebnis_text += f"📂 **#{kanal}** ({len(nachrichten)} Ergebnisse):\n"

        # Verwende KI (oder Heuristik) für intelligente Zusammenfassung pro Kanal
        kanal_zusammenfassung = await ki_suche(f"{suchbegriff} in #{kanal}", nachrichten[:5])
        ergebnis_text += f"{kanal_zusammenfassung}\n\n"

    return ergebnis_text

async def analysiere_nachricht_inhalt(nachricht_inhalt, urls_data=None):
    """Analysiert den Inhalt einer Nachricht und kategorisiert sie intelligent"""

    # Detaillierte Kanal-Kategorisierung basierend auf vorhandenen Kanälen
    kanal_kategorien = {
        # Webseiten und Design
        'webseiten': {
            'keywords': ['website', 'webseite', 'link', 'url', 'site', 'domain', 'online', 'web'],
            'url_indicators': ['font', 'design', 'template', 'css', 'html', 'javascript', 'framework'],
            'confidence_boost': 20
        },
        'ki-webseiten': {
            'keywords': ['ki', 'ai', 'artificial intelligence', 'machine learning', 'chatgpt', 'gemini', 'claude', 'openai'],
            'url_indicators': ['ai', 'ml', 'artificial', 'intelligence', 'chat', 'gpt', 'bot'],
            'confidence_boost': 25
        },
        'figma-plugins': {
            'keywords': ['figma', 'plugin', 'design', 'ui', 'ux', 'prototype', 'mockup'],
            'url_indicators': ['figma', 'plugin', 'design', 'ui', 'ux'],
            'confidence_boost': 30
        },

        # Bildung und Lernen
        'education-vids': {
            'keywords': ['tutorial', 'lernen', 'education', 'video', 'kurs', 'lesson', 'learn', 'study'],
            'url_indicators': ['youtube', 'tutorial', 'course', 'education', 'learn'],
            'confidence_boost': 25
        },
        'ableton-tutorial': {
            'keywords': ['ableton', 'live', 'musik', 'music', 'production', 'daw', 'audio'],
            'url_indicators': ['ableton', 'music', 'audio', 'production'],
            'confidence_boost': 35
        },
        'ableton-lessons': {
            'keywords': ['ableton', 'lesson', 'unterricht', 'musik', 'music', 'lernen'],
            'url_indicators': ['ableton', 'lesson', 'music'],
            'confidence_boost': 35
        },

        # Technik und Audio
        'audiotechnik': {
            'keywords': ['audio', 'sound', 'technik', 'equipment', 'mikrofon', 'lautsprecher', 'headphone'],
            'url_indicators': ['audio', 'sound', 'equipment', 'tech'],
            'confidence_boost': 30
        },
        'bme5': {
            'keywords': ['bme5', 'projekt', 'engineering', 'technik'],
            'url_indicators': ['engineering', 'tech', 'project'],
            'confidence_boost': 40
        },

        # Reise und Orte
        'travel': {
            'keywords': ['reise', 'travel', 'urlaub', 'vacation', 'trip', 'journey', 'flight', 'hotel'],
            'url_indicators': ['travel', 'booking', 'hotel', 'flight', 'trip'],
            'confidence_boost': 25
        },
        'portugal': {
            'keywords': ['portugal', 'lissabon', 'porto', 'lisboa', 'portuguese'],
            'url_indicators': ['portugal', 'lisboa', 'porto'],
            'confidence_boost': 40
        },
        'indonesien': {
            'keywords': ['indonesien', 'indonesia', 'bali', 'jakarta', 'indonesian'],
            'url_indicators': ['indonesia', 'bali', 'jakarta'],
            'confidence_boost': 40
        },
        'campingplätze-hier': {
            'keywords': ['camping', 'campingplatz', 'zelt', 'wohnmobil', 'caravan', 'outdoor'],
            'url_indicators': ['camping', 'outdoor', 'camp'],
            'confidence_boost': 35
        },

        # Persönliches und Organisation
        'bewerbungen': {
            'keywords': ['bewerbung', 'job', 'application', 'cv', 'lebenslauf', 'interview', 'karriere', 'work'],
            'url_indicators': ['job', 'career', 'application', 'linkedin'],
            'confidence_boost': 30
        },
        'bafög': {
            'keywords': ['bafög', 'studium', 'student', 'finanzierung', 'amt', 'antrag'],
            'url_indicators': ['bafoeg', 'student', 'study'],
            'confidence_boost': 40
        },
        'geschenk-ideen': {
            'keywords': ['geschenk', 'gift', 'present', 'birthday', 'geburtstag', 'weihnachten', 'christmas'],
            'url_indicators': ['gift', 'present', 'shop'],
            'confidence_boost': 30
        },
        'schulden-von': {
            'keywords': ['schulden', 'debt', 'geld', 'money', 'zahlung', 'payment', 'finanzen'],
            'url_indicators': ['finance', 'money', 'payment'],
            'confidence_boost': 35
        },

        # Projekte
        'ohmforyou': {
            'keywords': ['ohmforyou', 'ohm', 'projekt'],
            'url_indicators': ['ohm'],
            'confidence_boost': 50
        },
        'smarterblumentopf_eue': {
            'keywords': ['blumentopf', 'smart', 'iot', 'sensor', 'pflanze', 'plant'],
            'url_indicators': ['iot', 'smart', 'sensor'],
            'confidence_boost': 45
        },
        'growplan': {
            'keywords': ['growplan', 'grow', 'plan', 'wachstum'],
            'url_indicators': ['grow', 'plan'],
            'confidence_boost': 45
        },
        'android-lano': {
            'keywords': ['android', 'lano', 'app', 'mobile'],
            'url_indicators': ['android', 'mobile', 'app'],
            'confidence_boost': 40
        },
        'projektbericht-final': {
            'keywords': ['projektbericht', 'bericht', 'report', 'final', 'abschluss'],
            'url_indicators': ['report', 'project'],
            'confidence_boost': 40
        },

        # Sonstiges
        'mathe_2': {
            'keywords': ['mathe', 'mathematik', 'math', 'rechnen', 'formel', 'equation'],
            'url_indicators': ['math', 'calculator', 'formula'],
            'confidence_boost': 35
        },
        'mockups': {
            'keywords': ['mockup', 'design', 'template', 'ui', 'interface'],
            'url_indicators': ['mockup', 'template', 'design'],
            'confidence_boost': 35
        },
        'traning': {
            'keywords': ['training', 'sport', 'fitness', 'workout', 'exercise'],
            'url_indicators': ['fitness', 'sport', 'training'],
            'confidence_boost': 35
        },
        'tft-comps': {
            'keywords': ['tft', 'teamfight tactics', 'comp', 'composition', 'league'],
            'url_indicators': ['tft', 'teamfight', 'league'],
            'confidence_boost': 40
        },
        'ist': {
            'keywords': ['ist', 'information', 'system', 'technik'],
            'url_indicators': ['system', 'tech'],
            'confidence_boost': 30
        },
        'gedankenundso': {
            'keywords': ['gedanken', 'thoughts', 'idee', 'idea', 'nachdenken', 'philosophy'],
            'url_indicators': ['blog', 'thoughts', 'personal'],
            'confidence_boost': 25
        }
    }

    # Analysiere Nachrichteninhalt
    inhalt_lower = nachricht_inhalt.lower()
    kanal_scores = {}

    # Bewerte jeden Kanal
    for kanal, kategorie in kanal_kategorien.items():
        score = 0

        # Keyword-Matching im Nachrichteninhalt
        for keyword in kategorie['keywords']:
            if keyword in inhalt_lower:
                score += 10

        # URL-Metadaten-Analyse falls vorhanden
        if urls_data:
            for url_info in urls_data:
                title = url_info.get('title', '').lower()
                description = url_info.get('description', '').lower()
                domain = url_info.get('domain', '').lower()

                # Prüfe URL-Indikatoren
                for indicator in kategorie['url_indicators']:
                    if indicator in title or indicator in description or indicator in domain:
                        score += kategorie['confidence_boost']

                # Zusätzliche Keyword-Prüfung in URL-Metadaten
                for keyword in kategorie['keywords']:
                    if keyword in title or keyword in description:
                        score += 15

        if score > 0:
            kanal_scores[kanal] = score

    # Sortiere nach Score
    sortierte_kanaele = sorted(kanal_scores.items(), key=lambda x: x[1], reverse=True)

    return sortierte_kanaele

async def schlage_kanal_vor(nachricht):
    """Schlägt basierend auf Nachrichteninhalt einen passenden Kanal vor"""
    # Unterstützt sowohl String- als auch Dict-Input
    inhalt = ''
    if isinstance(nachricht, dict):
        inhalt = nachricht.get('content', '') or nachricht.get('inhalt', '')
    else:
        inhalt = str(nachricht or '')
    urls_data = []
    # Extrahiere URLs und deren Metadaten
    urls = finde_urls(inhalt)
    if urls:
        for url in urls:
            url_metadaten = await extrahiere_url_metadaten(url)
            urls_data.append(url_metadaten)
    # Analysiere Nachrichteninhalt
    kanal_vorschlaege = await analysiere_nachricht_inhalt(inhalt, urls_data)

    if not kanal_vorschlaege:
        return None

    # Nehme den besten Vorschlag
    bester_kanal, confidence = kanal_vorschlaege[0]

    # Mindest-Confidence für Vorschläge
    if confidence < 15:
        return None

    return {
        'kanal': bester_kanal,
        'confidence': confidence,
        'alternativen': kanal_vorschlaege[1:3],  # Top 2 Alternativen
        'grund': f"Erkannt basierend auf Inhalt und URLs (Confidence: {confidence})"
    }

# Hinweis: doppelter on_message Handler entfernt (siehe unten konsolidierte Version)

class KanalVorschlagView(discord.ui.View):
    def __init__(self, original_message, suggested_channel):
        super().__init__(timeout=300)  # 5 Minuten Timeout
        self.original_message = original_message
        self.suggested_channel = suggested_channel

    @discord.ui.button(label="✅ Verschieben", style=discord.ButtonStyle.green)
    async def move_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Finde den Zielkanal
        target_channel = discord.utils.get(interaction.guild.channels, name=self.suggested_channel)

        if not target_channel:
            await interaction.response.send_message(
                f"❌ Kanal #{self.suggested_channel} nicht gefunden!",
                ephemeral=True
            )
            return

        try:
            # Erstelle Embed für die verschobene Nachricht
            embed = discord.Embed(
                title="📤 Verschobene Nachricht",
                description=self.original_message.content,
                color=0x3498db,
                timestamp=self.original_message.created_at
            )

            embed.set_author(
                name=str(self.original_message.author),
                icon_url=self.original_message.author.display_avatar.url
            )

            embed.add_field(
                name="Ursprünglicher Kanal",
                value=f"#{self.original_message.channel.name}",
                inline=True
            )

            embed.add_field(
                name="Verschoben von",
                value=str(interaction.user),
                inline=True
            )

            # Sende Nachricht in Zielkanal
            await target_channel.send(embed=embed)

            # Bestätige die Verschiebung
            await interaction.response.send_message(
                f"✅ Nachricht erfolgreich nach #{self.suggested_channel} verschoben!",
                ephemeral=True
            )

            # Deaktiviere Buttons
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Fehler beim Verschieben: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.red)
    async def reject_suggestion(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "👍 Vorschlag abgelehnt. Die Nachricht bleibt hier.",
            ephemeral=True
        )

        # Deaktiviere Buttons
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="🔇 Ignorieren", style=discord.ButtonStyle.grey)
    async def ignore_suggestion(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Lösche die Vorschlagsnachricht
        await interaction.response.defer()
        await interaction.delete_original_response()

# Slash-Befehl für manuelle Kanalvorschläge
@tree.command(name="kanalvorschlag", description="Analysiert eine Nachricht und schlägt einen passenden Kanal vor")
async def kanalvorschlag_command(interaction: discord.Interaction, nachricht: str):
    """Analysiert eine Nachricht und schlägt einen passenden Kanal vor"""

    nachricht_data = {
        'content': nachricht,
        'author': str(interaction.user),
        'channel': interaction.channel.name if interaction.guild else 'DM'
    }

    vorschlag = await schlage_kanal_vor(nachricht_data)

    if not vorschlag:
        embed = discord.Embed(
            title="🤔 Kein Kanalvorschlag",
            description="Ich konnte keinen passenden Kanal für diese Nachricht finden.",
            color=0xffa500
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Erstelle Embed für Kanalvorschlag
    embed = discord.Embed(
        title="🎯 Kanalvorschlag",
        description=f"Diese Nachricht würde gut in **#{vorschlag['kanal']}** passen!",
        color=0x00ff00
    )

    embed.add_field(
        name="Analysierte Nachricht",
        value=nachricht[:200] + "..." if len(nachricht) > 200 else nachricht,
        inline=False
    )

    embed.add_field(
        name="Grund",
        value=vorschlag['grund'],
        inline=False
    )

    if vorschlag['alternativen']:
        alternativen_text = ", ".join([f"#{alt[0]} ({alt[1]} Punkte)" for alt in vorschlag['alternativen']])
        embed.add_field(
            name="Alternative Kanäle",
            value=alternativen_text,
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

def finde_urls(text: str) -> list:
    """Findet alle URLs in einem Text"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)

# Event, das zeigt, wenn der Bot bereit ist
@bot.event
async def on_ready():
    """Wird ausgeführt, wenn der Bot erfolgreich gestartet ist"""
    try:
        print(f"{bot.user} ist online und bereit!")
        print(f"Bot ist in {len(bot.guilds)} Server(n) aktiv")

        # Lade gespeicherte Nachrichten
        lade_nachrichten()
        print(f"📚 {len(gesammelte_nachrichten)} gespeicherte Nachrichten geladen")

        # Synchronisiere Slash-Befehle mit Discord
        synced = await tree.sync()
        print(f"✅ Erfolgreich {len(synced)} Slash Command(s) synchronisiert")

        # Lade historische Nachrichten aus allen Kanälen
        await lade_historische_nachrichten()

        print("🚀 Bot ist vollständig bereit!")

    except Exception as e:
        print(f"❌ Fehler beim Synchronisieren der Befehle: {e}")

# Event, das auf jede neue Nachricht reagiert
# Event-Handler für neue Nachrichten
@bot.event
async def on_message(message):
    """Sammelt automatisch alle Nachrichten für die KI-Wissensdatenbank und ermöglicht Dialoge in Threads"""
    try:
        # Ignoriere Bot-Nachrichten und eigene Nachrichten
        if message.author.bot:
            return

        # Ignoriere leere Nachrichten oder nur Attachments
        if not message.content.strip() and not message.attachments:
            return

        # Kontinuierlicher Dialog in Threads: antworte mit kanalgefilterter Suche
        try:
            if isinstance(message.channel, discord.Thread):
                ctx = thread_contexts.get(message.channel.id)
                if ctx:
                    antwort_text, _ = await kanalgefilterte_suche(message.content or ctx['suchbegriff'], ctx['kanaele'])
                    embed = discord.Embed(
                        title="🧵 Thread-Antwort",
                        description=antwort_text,
                        color=0x0099ff,
                        timestamp=datetime.now()
                    )
                    embed.add_field(
                        name="🧭 Kontext",
                        value=f"Basisfrage: {ctx['suchbegriff']}\nKanäle: " + ", ".join([f"#{k}" for k in ctx['kanaele']]),
                        inline=False
                    )
                    top_links_thread = extrahiere_top_links(message.content or ctx['suchbegriff'], ctx['kanaele'], limit=5)
                    if top_links_thread:
                        links_text = "\n".join([f"[{l['title']}]({l['url']}) · {l['domain']}" for l in top_links_thread])
                        embed.add_field(name="🔗 Top Links", value=links_text[:1024], inline=False)
                    icon_file = apply_embed_icon(embed, "question", mode="author", author_name="Thread-Antwort")
                    if icon_file:
                        await message.channel.send(embed=embed, file=icon_file)
                    else:
                        await message.channel.send(embed=embed)
        except Exception as e:
            print(f"Fehler im Thread-Dialog: {e}")

        # OPTION: Nur Nachrichten in bestimmten Kanälen sammeln (auskommentiert für alle Kanäle)
        # GEWUENSCHTE_CHANNEL_IDS = [123456789, 987654321]  # Ersetze mit deinen Channel-IDs
        # if message.channel.id not in GEWUENSCHTE_CHANNEL_IDS:
        #     return

        # URLs in der Nachricht finden und Metadaten extrahieren
        urls_in_message = finde_urls(message.content)
        url_metadaten = []

        for url in urls_in_message:
            metadaten = await extrahiere_url_metadaten(url)
            url_metadaten.append({
                'url': url,
                'title': metadaten['title'],
                'description': metadaten['description'],
                'domain': metadaten['domain']
            })

        # Erstelle Nachrichtendaten-Struktur
        nachricht_data = {
            'id': message.id,
            'autor': str(message.author),
            'autor_id': message.author.id,
            'channel': message.channel.name if hasattr(message.channel, 'name') else 'DM',
            'channel_id': message.channel.id,
            'guild': message.guild.name if message.guild else 'DM',
            'guild_id': message.guild.id if message.guild else None,
            'inhalt': message.content,
            'zeitstempel': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'attachments': [att.url for att in message.attachments] if message.attachments else [],
            'link': message.jump_url,
            'urls': url_metadaten  # Neue Feld für URL-Metadaten
        }

        # Füge zur globalen Liste hinzu
        gesammelte_nachrichten.append(nachricht_data)

        # Speichere Nachrichten nach jeder neuen Nachricht
        speichere_nachrichten()

        # Begrenze die Anzahl gespeicherter Nachrichten (für Performance)
        MAX_NACHRICHTEN = 10000
        if len(gesammelte_nachrichten) > MAX_NACHRICHTEN:
            # Entferne die ältesten 1000 Nachrichten
            gesammelte_nachrichten[:1000] = []
            print(f"Nachrichtenlimit erreicht. Älteste 1000 Nachrichten entfernt. Aktuelle Anzahl: {len(gesammelte_nachrichten)}")

        # Kanalvorschläge nur in bestimmten Kanälen anbieten
        if hasattr(message.channel, 'name') and message.channel.name in ['general', 'sachen']:
            # Analysiere Nachricht und schlage Kanal vor
            vorschlag = await schlage_kanal_vor(message.content)

            if vorschlag and vorschlag['kanal'] != message.channel.name:
                # Erstelle Embed für Kanalvorschlag
                embed = discord.Embed(
                    title="🎯 Kanalvorschlag",
                    description=f"Diese Nachricht würde gut in **#{vorschlag['kanal']}** passen!",
                    color=0x00ff00
                )

                embed.add_field(
                    name="Analysierte Nachricht",
                    value=message.content[:200] + "..." if len(message.content) > 200 else message.content,
                    inline=False
                )

                embed.add_field(
                    name="Grund",
                    value=vorschlag['grund'],
                    inline=False
                )

                if vorschlag['alternativen']:
                    alternativen_text = ", ".join([f"#{alt[0]} ({alt[1]} Punkte)" for alt in vorschlag['alternativen']])
                    embed.add_field(
                        name="Alternative Kanäle",
                        value=alternativen_text,
                        inline=False
                    )

                # Erstelle View mit Buttons
                view = KanalVorschlagView(message, vorschlag['kanal'])

                # Sende Vorschlag als Antwort auf die ursprüngliche Nachricht
                await message.reply(embed=embed, view=view)

        # Debug-Log für URLs
        if url_metadaten:
            print(f"🔗 URLs gefunden in Nachricht von {message.author}: {[meta['title'] for meta in url_metadaten]}")

        # Debug-Log (optional, kann entfernt werden für weniger Spam)
        if len(gesammelte_nachrichten) % 100 == 0:  # Nur jede 100. Nachricht loggen
            print(f"📝 {len(gesammelte_nachrichten)} Nachrichten gesammelt")

    except Exception as e:
        print(f"Fehler beim Sammeln der Nachricht: {e}")
        # Fehler nicht an den Benutzer weiterleiten, da dies ein Hintergrundprozess ist



# Ein einfacher Slash-Befehl zum Testen
@tree.command(name="hallo", description="Der Bot grüßt dich!")
async def hallo_command(interaction: discord.Interaction):
    """Einfacher Begrüßungsbefehl zum Testen der Bot-Funktionalität"""
    try:
        embed = discord.Embed(
            title="👋 Hallo!",
            description=f"Hallo {interaction.user.mention}! Ich bin dein KI-Bot und sammle Nachrichten für intelligente Suchen.",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="🤖 Verfügbare Befehle",
            value="• `/suche` - Durchsuche gesammelte Nachrichten\n• `/frage` - Stelle KI-Fragen zu den Nachrichten\n• `/stats` - Zeige Statistiken\n• `/clear` - Lösche alle Nachrichten (Admin)",
            inline=False
        )
        embed.add_field(
            name="📊 Status",
            value=f"**{len(gesammelte_nachrichten):,}** Nachrichten gesammelt",
            inline=True
        )
        embed.set_footer(text="Powered by Gemini 2.5 Flash Lite")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        print(f"Fehler in hallo_command: {e}")
        await send_error_embed(interaction, "Fehler", "❌ Ein Fehler ist aufgetreten.")

# Hilfsfunktion für KI-gestützte Suche
# Rate Limiting für kostenlose Gemini API (15 Anfragen pro Minute)
last_api_call = 0
# Reduzierte Wartezeit für das schnellere gemini-2.5-flash-lite Modell
API_CALL_DELAY = 3  # 3 Sekunden zwischen API-Aufrufen (optimiert für 2.5-flash-lite)

async def migriere_bestehende_nachrichten():
    """Migriert bestehende Nachrichten und extrahiert URL-Metadaten"""
    global gesammelte_nachrichten

    print("🔄 Starte Migration der bestehenden Nachrichten...")
    migrierte_nachrichten = 0
    urls_extrahiert = 0

    for nachricht in gesammelte_nachrichten:
        # Prüfe ob die Nachricht bereits das urls-Feld hat
        if 'urls' not in nachricht:
            nachricht['urls'] = []

        # Prüfe ob die Nachricht URLs im Inhalt hat
        if nachricht.get('inhalt'):
            urls = finde_urls(nachricht['inhalt'])
            if urls:
                print(f"📝 Extrahiere Metadaten für {len(urls)} URL(s) aus Nachricht von {nachricht.get('autor', 'Unbekannt')}")

                for url in urls:
                    try:
                        metadaten = await extrahiere_url_metadaten(url)
                        if metadaten:
                            nachricht['urls'].append(metadaten)
                            urls_extrahiert += 1
                            print(f"  ✅ {metadaten['title']} ({metadaten['domain']})")

                        # Kleine Pause um Server nicht zu überlasten
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"  ❌ Fehler bei URL {url}: {e}")

                migrierte_nachrichten += 1

    # Speichere die migrierten Daten
    speichere_nachrichten()

    print(f"✅ Migration abgeschlossen!")
    print(f"📊 {migrierte_nachrichten} Nachrichten migriert")
    print(f"🔗 {urls_extrahiert} URL-Metadaten extrahiert")

    return migrierte_nachrichten, urls_extrahiert

async def safe_gemini_call(prompt: str) -> str:
    """Sichere Gemini API-Aufrufe mit Rate Limiting für kostenlose Version"""
    global last_api_call
    # Wenn kein API-Key gesetzt ist, KI-Funktion freundlich deaktivieren
    if not KI_ENABLED or model is None:
        return "🔑 Kein Gemini API-Schlüssel gesetzt. KI-Funktionen sind derzeit deaktiviert."

    try:
        # Rate Limiting: Warte mindestens 4 Sekunden zwischen API-Aufrufen
        current_time = time.time()
        time_since_last_call = current_time - last_api_call
        if time_since_last_call < API_CALL_DELAY:
            wait_time = API_CALL_DELAY - time_since_last_call
            await asyncio.sleep(wait_time)

        # API-Aufruf
        response = await asyncio.to_thread(model.generate_content, prompt)
        last_api_call = time.time()

        return response.text

    except Exception as e:
        error_msg = str(e).lower()
        if "quota" in error_msg or "rate" in error_msg or "limit" in error_msg:
            return "⏳ **API-Limit erreicht** - Bitte warte einen Moment und versuche es erneut. (Kostenlose Gemini API hat Limits)"
        elif "api_key" in error_msg:
            return "🔑 **API-Schlüssel Fehler** - Bitte überprüfe deinen Gemini API-Schlüssel in der .env Datei"
        else:
            return f"❌ **KI-Fehler:** {str(e)}"

async def ki_suche(suchbegriff: str, nachrichten_kontext: list) -> str:
    """Verwendet Gemini AI für intelligente Suche und Antworten"""
    # Strukturierter Kontext: Top-N Nachrichten + Link-Snippets (begrenzt für Performance)
    kontext_items = []
    for nachricht in nachrichten_kontext[:8]:
        kanal = nachricht.get('channel', 'unknown')
        autor = nachricht.get('autor', 'Unbekannt')
        ts = nachricht.get('zeitstempel', '')
        inhalt = (nachricht.get('inhalt', '') or '').strip()
        if len(inhalt) > 220:
            inhalt = inhalt[:220] + "..."
        lines = [f"- Kanal #{kanal} · {ts} · {autor}:", f"  {inhalt}"]
        urls = nachricht.get('urls') or []
        if urls:
            lines.append("  📎 Links:")
            for url_data in urls[:3]:
                titel = (url_data.get('title') or '').strip()
                domain = (url_data.get('domain') or '').strip()
                beschr = (url_data.get('description') or '').strip()
                if beschr and beschr.lower() != 'keine beschreibung verfügbar':
                    if len(beschr) > 120:
                        beschr = beschr[:120] + "..."
                    lines.append(f"    • {titel} · {domain} — {beschr}")
                else:
                    lines.append(f"    • {titel} · {domain}")
        kontext_items.append("\n".join(lines))

    kontext_text = "\n".join(kontext_items)

    # Verbesserter Prompt für Gemini: klare Richtlinien und strukturiertes Ausgabeformat
    prompt = f"""
Du bist ein hilfreicher Assistent für eine persönliche Wissensdatenbank.
Beantworte die Suchanfrage basierend AUSSCHLIESSLICH auf den folgenden Discord-Nachrichten und Link-Metadaten.

Suchanfrage: "{suchbegriff}"

Kontextnachrichten:
{kontext_text}

Richtlinien:
- Analysiere Nachrichtentexte und Link-Metadaten (Titel, Beschreibungen, Domains).
- Bevorzuge neuere und mehrfach erwähnte Inhalte, wenn mehrere Optionen vorhanden sind.
- Nutze verwandte Begriffe (z. B. "Font" ↔ "Schriftart", "Typografie"), aber erfinde keine Fakten.
- Wenn keine relevanten Informationen vorhanden sind, sage das ehrlich.

Ausgabeformat:
1) Antwort: Starte mit der Hauptantwort in 1–2 Sätzen (max. 900 Zeichen), klar und direkt.
2) Belege: Bis zu 4 Bulletpoints mit sehr kurzen Zitaten/Paraphrasen aus relevanten Nachrichten (max. 140 Zeichen je Punkt).
3) Links: Wenn hilfreich, bis zu 3 relevante Einträge als "Titel (Domain) — kurzer Hinweis".

WICHTIG:
- Keine Vermutungen außerhalb des Kontexts; vermeide Halluzinationen.
- Wenn der Kontext unzureichend ist, schreibe: "Keine ausreichend relevanten Informationen gefunden." und nenne ggf. welche Begriffe im Kontext vorkamen.
"""

    return await safe_gemini_call(prompt)

# Neue Helferfunktionen für Threads und Top-Links
async def kanalgefilterte_suche(suchbegriff: str, kanaele: list[str]) -> tuple[str, list[str]]:
    """Suche nur innerhalb der angegebenen Kanäle. Fallback auf globale Suche, wenn nichts gefunden.
    Gibt den Ergebnistext und die Liste der Kanäle mit Treffern zurück. Nutzt token-basiertes Matching mit einfachem Stemming und berücksichtigt URL-Metadaten."""
    if not kanaele:
        text = await hierarchische_suche(suchbegriff)
        return text, []

    tokens = extrahiere_schluesselwoerter(suchbegriff)
    kanal_ergebnisse: dict[str, list] = {}

    for kanal in kanaele:
        scored_nachrichten = []
        for nachricht in gesammelte_nachrichten:
            if nachricht.get('channel') != kanal:
                continue

            inhalt_lower = nachricht.get('inhalt', '').lower()
            score = 0
            # Treffer im Nachrichtentext
            score += sum(1 for tok in tokens if tok in inhalt_lower)

            # Treffer in URL-Metadaten
            urls = nachricht.get('urls') or []
            for url_data in urls:
                titel = url_data.get('title', '').lower()
                beschr = url_data.get('description', '').lower()
                domain = url_data.get('domain', '').lower()
                if any(tok in titel or tok in beschr or tok in domain for tok in tokens):
                    score += 1
                    break

            if score > 0:
                ts = nachricht.get('zeitstempel')
                try:
                    seen = _dt.strptime(ts, '%Y-%m-%d %H:%M:%S') if ts else _dt.min
                except Exception:
                    seen = _dt.min
                scored_nachrichten.append((score, seen, nachricht))

        if scored_nachrichten:
            # Sortiere nach Score und Aktualität
            scored_nachrichten.sort(key=lambda x: (x[0], x[1]), reverse=True)
            kanal_ergebnisse[kanal] = [n for _, _, n in scored_nachrichten]

    if not kanal_ergebnisse:
        # Nichts in den gefilterten Kanälen gefunden -> globale Suche
        text = await hierarchische_suche(suchbegriff)
        return text, []

    # Erstelle KI-gestützte Zusammenfassung pro Kanal
    ergebnis_text = f"🔍 **Gefilterte Suchergebnisse für '{suchbegriff}':**\n\n"
    for kanal, nachrichten in kanal_ergebnisse.items():
        ergebnis_text += f"📂 **#{kanal}** ({len(nachrichten)} Ergebnisse):\n"
        kanal_zusammenfassung = await ki_suche(f"{suchbegriff} in #{kanal}", nachrichten[:5])
        ergebnis_text += f"{kanal_zusammenfassung}\n\n"

    kanaele_mit_treffern = list(kanal_ergebnisse.keys())
    return ergebnis_text, kanaele_mit_treffern

from datetime import datetime as _dt

def extrahiere_top_links(suchbegriff: str, kanaele: list[str] | None = None, limit: int = 5) -> list[dict]:
    """Extrahiert die Top-Links basierend auf dem Suchbegriff, optional gefiltert nach Kanälen.
    Nutzt token-basierte Scoring-Logik und berücksichtigt Aktualität."""
    tokens = extrahiere_schluesselwoerter(suchbegriff)
    link_stats: dict[str, dict] = {}

    for nachricht in gesammelte_nachrichten:
        # Optional nach Kanal filtern
        if kanaele and nachricht.get('channel') not in set(kanaele):
            continue

        inhalt_lower = nachricht.get('inhalt', '').lower()
        content_score = sum(1 for tok in tokens if tok in inhalt_lower)

        urls = nachricht.get('urls') or []
        for url_data in urls:
            titel = url_data.get('title', '').lower()
            beschr = url_data.get('description', '').lower()
            domain = url_data.get('domain', '').lower()

            meta_score = sum(1 for tok in tokens if tok in titel or tok in beschr or tok in domain)
            total_score = content_score + meta_score
            if total_score == 0:
                continue

            url = url_data.get('url') or f"https://{url_data.get('domain','')}"
            title_out = url_data.get('title') or 'Unbekannter Titel'
            domain_out = url_data.get('domain') or 'Unbekannte Domain'

            ts = nachricht.get('zeitstempel')
            try:
                seen = _dt.strptime(ts, '%Y-%m-%d %H:%M:%S') if ts else _dt.min
            except Exception:
                seen = _dt.min

            if url not in link_stats:
                link_stats[url] = {
                    'url': url,
                    'title': title_out,
                    'domain': domain_out,
                    'count': 1,
                    'last_seen': seen,
                    'score': total_score,
                }
            else:
                link_stats[url]['count'] += 1
                link_stats[url]['score'] += total_score
                if seen > link_stats[url]['last_seen']:
                    link_stats[url]['last_seen'] = seen

    # Sortiere nach Relevanz-Score, Häufigkeit, dann Aktualität
    sortierte = sorted(link_stats.values(), key=lambda x: (x['score'], x['count'], x['last_seen']), reverse=True)
    top = sortierte[:limit]
    return [{'url': t.get('url'), 'title': t.get('title'), 'domain': t.get('domain')} for t in top]

# Slash-Befehl zum Durchsuchen der gesammelten Nachrichten
@tree.command(name="suche", description="Durchsucht deine gesammelten Nachrichten nach einem Begriff")
async def suche_command(interaction: discord.Interaction, suchbegriff: str):
    """KI-gestützte Suche in gesammelten Nachrichten mit hierarchischer Kanal-Suche"""
    try:
        # Sofortige Antwort, da KI-Verarbeitung Zeit braucht
        await interaction.response.defer(thinking=True)

        if not gesammelte_nachrichten:
            embed = discord.Embed(
                title="📭 Noch keine Nachrichten gesammelt",
                description="Ich kann erst suchen, nachdem Nachrichten gesammelt wurden.",
                color=0xffa500
            )
            icon_file = apply_embed_icon(embed, "info", mode="author", author_name="Hinweis")
            if icon_file:
                await interaction.followup.send(embed=embed, file=icon_file)
            else:
                await interaction.followup.send(embed=embed)
            return

        # Verwende hierarchische Suche
        ergebnis = await hierarchische_suche(suchbegriff)

        # Formatierte Antwort senden
        embed = discord.Embed(
            title=f"🔍 Suchergebnisse für: {suchbegriff}",
            description=ergebnis,
            color=0x00ff00,
            timestamp=datetime.now()
        )

        # Zeige relevante Kanäle an
        relevante_kanaele = finde_relevante_kanaele(suchbegriff, gesammelte_nachrichten)
        embed.add_field(
            name="📂 Durchsuchte Kanäle",
            value=", ".join([f"#{kanal}" for kanal in relevante_kanaele[:10]]),
            inline=False
        )

        # Zeige Top-Links
        top_links = extrahiere_top_links(suchbegriff, relevante_kanaele, limit=5)
        if top_links:
            links_text = "\n".join([f"[{l['title']}]({l['url']}) · {l['domain']}" for l in top_links])
            embed.add_field(name="🔗 Top Links", value=links_text[:1024], inline=False)

        embed.set_footer(text=f"Durchsucht: {len(gesammelte_nachrichten)} Nachrichten")

        # Icon einbinden (Lucide: search)
        icon_file = apply_embed_icon(embed, "search", mode="author", author_name="Suchergebnisse")
        if icon_file:
            await interaction.followup.send(embed=embed, file=icon_file)
        else:
            await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Fehler in suche_command: {e}")
        await send_error_embed(interaction, "Fehler bei der Suche", "❌ Ein Fehler bei der Suche ist aufgetreten.")

# Neuer KI-Chat Befehl für natürlichsprachige Anfragen
@tree.command(name="frage", description="Stelle eine Frage zu deinen gesammelten Nachrichten")
async def frage_command(interaction: discord.Interaction, frage: str):
    """Natürlichsprachige KI-Anfragen mit hierarchischer Kanal-Suche"""
    try:
        # Sofortige Antwort, da KI-Verarbeitung Zeit braucht
        await interaction.response.defer(thinking=True)

        if not gesammelte_nachrichten:
            embed = discord.Embed(
                title="📭 Noch keine Nachrichten gesammelt",
                description="Der Bot muss erst Nachrichten sammeln, bevor ich Fragen beantworten kann.",
                color=0xffa500
            )
            icon_file = apply_embed_icon(embed, "info", mode="author", author_name="Hinweis")
            if icon_file:
                await interaction.followup.send(embed=embed, file=icon_file)
            else:
                await interaction.followup.send(embed=embed)
            return

        # Verwende kanalgefilterte KI-Suche für bessere Kontextualisierung
        relevante_kanaele = finde_relevante_kanaele(frage, gesammelte_nachrichten)
        antwort_text, treffer_kanaele = await kanalgefilterte_suche(frage, relevante_kanaele)

        # Formatierte Antwort als Embed
        embed = discord.Embed(
            title="🤖 KI-Antwort",
            description=antwort_text,
            color=0x0099ff,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="📝 Deine Frage",
            value=frage,
            inline=False
        )

        # Zeige relevante Kanäle an
        durchsuchte_text = ", ".join([f"#{kanal}" for kanal in treffer_kanaele[:10]]) if treffer_kanaele else "Globale Suche über alle Kanäle"
        embed.add_field(
            name="📂 Durchsuchte Kanäle",
            value=durchsuchte_text,
            inline=False
        )

        # Zeige Top-Links
        top_links = extrahiere_top_links(frage, treffer_kanaele or relevante_kanaele, limit=5)
        if top_links:
            links_text = "\n".join([f"[{l['title']}]({l['url']}) · {l['domain']}" for l in top_links])
            embed.add_field(name="🔗 Top Links", value=links_text[:1024], inline=False)

        # 📊 Qualitätsmetriken: einfache Trefferquote + Antwortlänge
        try:
            tokens = extrahiere_schluesselwoerter(frage)
            scan_kanaele = treffer_kanaele or relevante_kanaele
            total_scanned = sum(1 for n in gesammelte_nachrichten if n.get('channel') in scan_kanaele)
            matched = 0
            for n in gesammelte_nachrichten:
                if n.get('channel') not in scan_kanaele:
                    continue
                text = (n.get('inhalt') or '').lower()
                urls = n.get('urls') or []
                hit = any(t in text for t in tokens)
                if not hit and urls:
                    for u in urls:
                        td = " ".join([(u.get('title') or ''), (u.get('description') or ''), (u.get('domain') or '')]).lower()
                        if any(t in td for t in tokens):
                            hit = True
                            break
                if hit:
                    matched += 1
            hit_ratio = int(round((matched / total_scanned) * 100)) if total_scanned else 0
            qm_text = f"Trefferquote: {hit_ratio}% ({matched}/{total_scanned}) • Antwortlänge: {len(antwort_text)} Zeichen"
            embed.add_field(name="📊 Qualitätsmetriken", value=qm_text, inline=False)
        except Exception as _e:
            print(f"Qualitätsmetriken Fehler: {_e}")

        embed.set_footer(text=f"Basierend auf {len(gesammelte_nachrichten)} Nachrichten")

        # Icon einbinden (Lucide: question)
        icon_file = apply_embed_icon(embed, "question", mode="author", author_name="KI-Antwort")

        # Thread-Integration
        if ENABLE_THREADS and interaction.guild:
            try:
                perms = getattr(interaction, "app_permissions", None)
                if perms is None:
                    bot_member = interaction.guild.me
                    perms = interaction.channel.permissions_for(bot_member) if bot_member else interaction.channel.permissions_for(interaction.guild.default_role)
                # Diagnose: zeige Kanaltyp und Thread-Rechte
                try:
                    chan_type = getattr(getattr(interaction.channel, 'type', None), 'name', str(getattr(interaction.channel, 'type', '?')))
                except Exception:
                    chan_type = str(getattr(interaction.channel, 'type', '?'))
                print(f"Thread-Diagnose: Kanal={getattr(interaction.channel, 'name', '?')} Typ={chan_type} create_public_threads={getattr(perms, 'create_public_threads', None)} create_private_threads={getattr(perms, 'create_private_threads', None)} send_messages_in_threads={getattr(perms, 'send_messages_in_threads', None)}")
                thread_name = f"Frage: {frage[:80]}"
                if chan_type == 'forum':
                    try:
                        # Forum-Fallback: Erstelle einen Post (Thread) direkt im Forum-Kanal mit der KI-Antwort als Erstbeitrag
                        if icon_file:
                            thread = await interaction.channel.create_thread(
                                name=thread_name,
                                auto_archive_duration=THREAD_AUTO_ARCHIVE_MINUTES,
                                content=f"Thread für die Frage von {interaction.user.mention}. Weitere Rückfragen bitte hier posten.",
                                embeds=[embed],
                                files=[icon_file]
                            )
                        else:
                            thread = await interaction.channel.create_thread(
                                name=thread_name,
                                auto_archive_duration=THREAD_AUTO_ARCHIVE_MINUTES,
                                content=f"Thread für die Frage von {interaction.user.mention}. Weitere Rückfragen bitte hier posten.",
                                embeds=[embed]
                            )
                        # Speichere Thread-Kontext
                        thread_contexts[thread.id] = {
                            'suchbegriff': frage,
                            'kanaele': treffer_kanaele,
                            'created_by': interaction.user.id,
                            'created_at': datetime.now().isoformat()
                        }
                        # Optional Slowmode setzen
                        if THREAD_SLOWMODE and THREAD_SLOWMODE > 0:
                            try:
                                await thread.edit(slowmode_delay=THREAD_SLOWMODE)
                            except Exception as e:
                                print(f"Fehler beim Setzen von Slowmode für Forum-Thread: {e}")
                        # Bestätigungsnachricht
                        try:
                            await interaction.followup.send(content=f"🧵 Thread erstellt: {thread.mention}", ephemeral=True)
                        except Exception as e:
                            print(f"Followup-Bestätigung im Forum-Kanal fehlgeschlagen: {e}")
                    except Exception as e:
                        print(f"Fehler beim Erstellen des Forum-Threads: {e}")
                        # Fallback: normale Antwort ohne Thread
                        if icon_file:
                            await interaction.followup.send(embed=embed, file=icon_file)
                        else:
                            await interaction.followup.send(embed=embed)
                elif getattr(perms, "create_public_threads", False) and getattr(perms, "send_messages_in_threads", False):
                    # Sende die Antwortnachricht und erstelle daraus einen Public Thread
                    if icon_file:
                        msg = await interaction.followup.send(embed=embed, file=icon_file, wait=True)
                    else:
                        msg = await interaction.followup.send(embed=embed, wait=True)
                    # Erstelle Thread basierend auf der gesendeten Nachricht (WebhookMessage -> PartialMessage)
                    partial_msg = interaction.channel.get_partial_message(msg.id)
                    try:
                        thread = await partial_msg.create_thread(
                            name=thread_name,
                            auto_archive_duration=THREAD_AUTO_ARCHIVE_MINUTES
                        )
                    except Exception as e:
                        print(f"Fehler bei create_thread für Nachricht: {e}")
                        thread = None
                    if thread:
                        # Speichere Thread-Kontext
                        thread_contexts[thread.id] = {
                            'suchbegriff': frage,
                            'kanaele': treffer_kanaele,
                            'created_by': interaction.user.id,
                            'created_at': datetime.now().isoformat()
                        }
                        # Optional Slowmode setzen
                        if THREAD_SLOWMODE and THREAD_SLOWMODE > 0:
                            try:
                                await thread.edit(slowmode_delay=THREAD_SLOWMODE)
                            except Exception as e:
                                print(f"Fehler beim Setzen von Slowmode für Thread: {e}")
                        # Begrüßungsnachricht im Thread
                        await thread.send(f"Thread für die Frage von {interaction.user.mention}. Weitere Rückfragen bitte hier posten.")
                        # Ephemere Bestätigung
                        try:
                            await interaction.followup.send(content=f"🧵 Thread erstellt: {thread.mention}", ephemeral=True)
                        except Exception as e:
                            print(f"Followup-Bestätigung im Public-Thread fehlgeschlagen: {e}")
                else:
                    # Fallback: keine Berechtigungen -> normale Antwort
                    if icon_file:
                        await interaction.followup.send(embed=embed, file=icon_file)
                    else:
                        await interaction.followup.send(embed=embed)
            except Exception as e:
                print(f"Fehler beim Erstellen des Threads: {e}")
                try:
                    if icon_file:
                        await interaction.followup.send(embed=embed, file=icon_file)
                    else:
                        await interaction.followup.send(embed=embed)
                except:
                    pass
        else:
            # Threads deaktiviert oder DM-Kontext -> normale Antwort
            if icon_file:
                await interaction.followup.send(embed=embed, file=icon_file)
            else:
                await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Fehler in frage_command: {e}")
        await send_error_embed(interaction, "Fehler bei der KI-Anfrage", "❌ Ein Fehler bei der KI-Anfrage ist aufgetreten.")

@tree.command(name="stats", description="Zeigt Statistiken über die gesammelten Nachrichten")
async def stats_command(interaction: discord.Interaction):
    """Zeigt detaillierte Statistiken über die gesammelten Nachrichten"""
    try:
        await interaction.response.defer()

        if not gesammelte_nachrichten:
            embed = discord.Embed(
                title="📊 Statistiken",
                description="📭 Noch keine Nachrichten gesammelt!",
                color=0xffa500
            )
            # Icon (info/warn)
            icon_file = apply_embed_icon(embed, "info", mode="author", author_name="Statistiken")
            if icon_file:
                await interaction.followup.send(embed=embed, file=icon_file)
            else:
                await interaction.followup.send(embed=embed)
            return

        # Statistiken berechnen
        total_nachrichten = len(gesammelte_nachrichten)

        # Autoren-Statistiken
        autoren_count = {}
        channel_count = {}

        for nachricht in gesammelte_nachrichten:
            autor = nachricht.get('autor', 'Unbekannt')
            channel = nachricht.get('channel', 'Unbekannt')

            autoren_count[autor] = autoren_count.get(autor, 0) + 1
            channel_count[channel] = channel_count.get(channel, 0) + 1

        # Top 5 Autoren
        top_autoren = sorted(autoren_count.items(), key=lambda x: x[1], reverse=True)[:5]
        top_channels = sorted(channel_count.items(), key=lambda x: x[1], reverse=True)[:5]

        # Zeitraum berechnen
        if gesammelte_nachrichten:
            erste_nachricht = gesammelte_nachrichten[0].get('zeitstempel', 'Unbekannt')
            letzte_nachricht = gesammelte_nachrichten[-1].get('zeitstempel', 'Unbekannt')
        else:
            erste_nachricht = letzte_nachricht = 'Unbekannt'

        # Embed erstellen
        embed = discord.Embed(
            title="📊 Nachrichten-Statistiken",
            color=0x00ff00,
            timestamp=datetime.now()
        )

        embed.add_field(
            name="📈 Gesamt",
            value=f"**{total_nachrichten:,}** Nachrichten gesammelt",
            inline=False
        )

        if top_autoren:
            autoren_text = "\n".join([f"**{autor}**: {count:,} Nachrichten" for autor, count in top_autoren])
            embed.add_field(
                name="👥 Top Autoren",
                value=autoren_text,
                inline=True
            )

        if top_channels:
            channels_text = "\n".join([f"**#{channel}**: {count:,} Nachrichten" for channel, count in top_channels])
            embed.add_field(
                name="📺 Top Channels",
                value=channels_text,
                inline=True
            )

        embed.add_field(
            name="⏰ Zeitraum",
            value=f"**Von:** {erste_nachricht}\n**Bis:** {letzte_nachricht}",
            inline=False
        )

        embed.set_footer(text="Statistiken werden live aktualisiert")

        # Icon für Statistiken
        icon_file = apply_embed_icon(embed, "bar-chart", mode="author", author_name="Statistiken")
        if icon_file:
            await interaction.followup.send(embed=embed, file=icon_file)
        else:
            await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Fehler in stats_command: {e}")
        await send_error_embed(interaction, "Fehler beim Laden der Statistiken", "❌ Fehler beim Laden der Statistiken.")

@tree.command(name="clear", description="Löscht alle gesammelten Nachrichten (nur für Admins)")
async def clear_command(interaction: discord.Interaction):
    """Löscht alle gesammelten Nachrichten - nur für Administratoren"""
    try:
        # Überprüfe Admin-Berechtigung
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Keine Berechtigung",
                description="Nur Administratoren können die Nachrichten-Datenbank löschen.",
                color=0xff0000
            )
            # Icon (alert)
            icon_file = apply_embed_icon(embed, "alert-triangle", mode="author", author_name="Berechtigung")
            await interaction.response.send_message(embed=embed, ephemeral=True, file=icon_file) if icon_file else await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Anzahl der zu löschenden Nachrichten
        anzahl_nachrichten = len(gesammelte_nachrichten)

        if anzahl_nachrichten == 0:
            embed = discord.Embed(
                title="📭 Bereits leer",
                description="Es sind keine Nachrichten zum Löschen vorhanden.",
                color=0xffa500
            )
            # Icon (info)
            icon_file = apply_embed_icon(embed, "info", mode="author", author_name="Hinweis")
            if icon_file:
                await interaction.followup.send(embed=embed, file=icon_file)
            else:
                await interaction.followup.send(embed=embed)
            return

        # Nachrichten löschen
        gesammelte_nachrichten.clear()

        # Bestätigung
        embed = discord.Embed(
            title="🗑️ Datenbank geleert",
            description=f"**{anzahl_nachrichten:,}** Nachrichten wurden erfolgreich gelöscht.",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="👤 Gelöscht von",
            value=interaction.user.mention,
            inline=True
        )
        embed.set_footer(text="Die Nachrichtensammlung beginnt von neuem")

        # Icon (trash / bar-chart nicht vorhanden, daher alert oder info passend)
        icon_file = apply_embed_icon(embed, "bar-chart", mode="author", author_name="Bereinigung")
        if icon_file:
            await interaction.followup.send(embed=embed, file=icon_file)
        else:
            await interaction.followup.send(embed=embed)

        # Log-Nachricht für Transparenz
        print(f"Nachrichten-Datenbank geleert von {interaction.user} ({interaction.user.id})")

    except Exception as e:
        print(f"Fehler in clear_command: {e}")
        await send_error_embed(interaction, "Fehler beim Löschen", "❌ Fehler beim Löschen der Nachrichten.")

async def lade_historische_nachrichten():
    """Lädt historische Nachrichten aus allen Kanälen beim Bot-Start"""
    try:
        print("🔄 Lade historische Nachrichten...")
        total_loaded = 0

        for guild in bot.guilds:
            print(f"📂 Lade Nachrichten aus Server: {guild.name}")

            for channel in guild.text_channels:
                try:
                    # Überprüfe Bot-Berechtigungen
                    if not channel.permissions_for(guild.me).read_message_history:
                        print(f"⚠️  Keine Berechtigung für #{channel.name}")
                        continue

                    print(f"📝 Lade aus #{channel.name}...")
                    loaded_count = 0

                    # Lade die letzten 500 Nachrichten pro Kanal (anpassbar)
                    async for message in channel.history(limit=500):
                        # Ignoriere Bot-Nachrichten
                        if message.author.bot:
                            continue

                        # Ignoriere leere Nachrichten
                        if not message.content.strip() and not message.attachments:
                            continue

                        # Überprüfe ob Nachricht bereits existiert
                        if any(n['id'] == message.id for n in gesammelte_nachrichten):
                            continue

                        # Erstelle Nachrichtendaten
                        nachricht_data = {
                            'id': message.id,
                            'autor': str(message.author),
                            'autor_id': message.author.id,
                            'channel': channel.name,
                            'channel_id': channel.id,
                            'guild': guild.name,
                            'guild_id': guild.id,
                            'inhalt': message.content,
                            'zeitstempel': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                            'attachments': [att.url for att in message.attachments] if message.attachments else [],
                            'link': message.jump_url,
                            'urls': url_metadaten  # Neue Feld für URL-Metadaten
                        }

                        gesammelte_nachrichten.append(nachricht_data)
                        loaded_count += 1
                        total_loaded += 1

                    if loaded_count > 0:
                        print(f"✅ {loaded_count} Nachrichten aus #{channel.name} geladen")

                    # Kleine Pause zwischen Kanälen (Rate Limiting)
                    await asyncio.sleep(0.5)

                except Exception as e:
                    print(f"❌ Fehler beim Laden aus #{channel.name}: {e}")
                    continue

        # Sortiere Nachrichten nach Zeitstempel
        gesammelte_nachrichten.sort(key=lambda x: x['zeitstempel'])

        # Begrenze auf MAX_NACHRICHTEN
        MAX_NACHRICHTEN = 10000
        if len(gesammelte_nachrichten) > MAX_NACHRICHTEN:
            # Behalte die neuesten Nachrichten
            gesammelte_nachrichten[:] = gesammelte_nachrichten[-MAX_NACHRICHTEN:]
            print(f"📊 Nachrichten auf {MAX_NACHRICHTEN} begrenzt (neueste behalten)")

        print(f"🎉 Historische Nachrichten geladen: {total_loaded} neue Nachrichten")
        print(f"📊 Gesamt gesammelte Nachrichten: {len(gesammelte_nachrichten)}")

        # Speichere die geladenen Nachrichten
        speichere_nachrichten()

    except Exception as e:
        print(f"❌ Fehler beim Laden historischer Nachrichten: {e}")

@tree.command(name="migrate", description="Migriert bestehende Nachrichten und extrahiert URL-Metadaten (nur für Admins)")
async def migrate_command(interaction: discord.Interaction):
    """Slash Command für die Migration bestehender Nachrichten"""
    # Prüfe Admin-Berechtigung
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Nur Administratoren können diesen Befehl verwenden!", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        migrierte_nachrichten, urls_extrahiert = await migriere_bestehende_nachrichten()

        embed = discord.Embed(
            title="🔄 Migration abgeschlossen",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📊 Migrierte Nachrichten", value=str(migrierte_nachrichten), inline=True)
        embed.add_field(name="🔗 Extrahierte URLs", value=str(urls_extrahiert), inline=True)
        embed.add_field(name="✅ Status", value="Erfolgreich abgeschlossen", inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Fehler bei der Migration: {e}")

@tree.command(name="sync", description="Lädt historische Nachrichten aus allen Kanälen (nur für Admins)")
async def sync_command(interaction: discord.Interaction):
    """Manueller Befehl zum Laden historischer Nachrichten"""
    try:
        # Überprüfe Admin-Berechtigung
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Nur Administratoren können diesen Befehl verwenden!", ephemeral=True)
            return

        # Sofortige Antwort, da das Laden Zeit braucht
        await interaction.response.defer(thinking=True)

        # Aktuelle Anzahl vor dem Laden
        vorher_anzahl = len(gesammelte_nachrichten)

        # Lade historische Nachrichten
        await lade_historische_nachrichten()

        # Neue Anzahl nach dem Laden
        nachher_anzahl = len(gesammelte_nachrichten)
        neue_nachrichten = nachher_anzahl - vorher_anzahl

        # Erstelle Antwort-Embed
        embed = discord.Embed(
            title="📚 Nachrichtensynchronisation abgeschlossen",
            color=0x00ff00,
            timestamp=datetime.now()
        )

        embed.add_field(
            name="📊 Statistiken",
            value=f"**Vorher:** {vorher_anzahl:,} Nachrichten\n"
                  f"**Nachher:** {nachher_anzahl:,} Nachrichten\n"
                  f"**Neu geladen:** {neue_nachrichten:,} Nachrichten",
            inline=False
        )

        if neue_nachrichten > 0:
            embed.add_field(
                name="✅ Status",
                value="Historische Nachrichten erfolgreich geladen!",
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ Status",
                value="Keine neuen Nachrichten gefunden.",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Fehler beim Synchronisieren",
            description=f"Ein Fehler ist aufgetreten: {str(e)}",
            color=0xff0000
        )
        try:
            await interaction.followup.send(embed=error_embed)
        except:
            pass

# Starte den Bot mit dem Token
# WICHTIG: Ersetze den Token durch deinen eigenenen Bot-Token!
import sys
if not DISCORD_TOKEN:
    print("❌ Kein DISCORD_TOKEN gefunden. Bitte setze den Token in deiner .env-Datei.")
    sys.exit(1)

bot.run(DISCORD_TOKEN)
