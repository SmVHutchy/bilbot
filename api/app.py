"""
BilBot API - RESTful Schnittstelle für Discord-Nachrichtenverwaltung

Diese API bietet Endpunkte zum Verwalten von Discord-Nachrichten, die vom BilBot gesammelt wurden,
sowie Demo-Endpunkte für Kunden und Rechnungen. Sie ermöglicht das Abrufen, Suchen und Analysieren
von Nachrichten über eine standardisierte HTTP-Schnittstelle.

Hauptfunktionen:
- Abrufen von Nachrichten mit Paginierung
- Suche in Nachrichten nach Text, Kanal oder Autor
- Statistiken über gesammelte Nachrichten
- Demo-Endpunkte für Kunden- und Rechnungsverwaltung
"""

from fastapi import FastAPI, HTTPException, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from uuid import uuid4
import json
import os
from datetime import datetime, timezone
import logging
import traceback

# ASGI-Wrapper zum Entfernen eines festen Pfadpräfixes (z.B. /api)
class PrefixStripper:
    def __init__(self, app, prefix: str = "/api"):
        self.app = app
        # Entferne abschließenden Slash für konsistente Vergleiche
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope, receive, send):
        # Nur HTTP-Requests beeinflussen
        if scope.get("type") == "http":
            path = scope.get("path", "")
            # Wenn der Pfad exakt dem Präfix entspricht oder damit beginnt, Präfix entfernen
            if path == self.prefix or path.startswith(self.prefix + "/"):
                new_path = path[len(self.prefix):]
                scope["path"] = new_path if new_path else "/"
        # Anfrage an die eigentliche FastAPI-App weiterleiten
        await self.app(scope, receive, send)

# Logger-Konfiguration
logger = logging.getLogger("bilbot.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# FastAPI-Anwendung mit Metadaten
app = FastAPI(
    title="BilBot API",
    description="""
    ## BilBot API Dokumentation

    Diese API bietet Zugriff auf Discord-Nachrichten, die vom BilBot gesammelt wurden,
    sowie Demo-Endpunkte für Kunden- und Rechnungsverwaltung.

    ### Hauptfunktionen:

    * **Nachrichten-Endpunkte**: Abfragen, Suchen und Statistiken zu Discord-Nachrichten
    * **Kunden-Endpunkte**: Demo-Endpunkte für Kundenverwaltung
    * **Rechnungs-Endpunkte**: Demo-Endpunkte für Rechnungsverwaltung

    Alle Daten werden im JSON-Format zurückgegeben.
    """,
    version="1.0.0",
    contact={
        "name": "BilBot Support",
        "url": "https://github.com/yourusername/bilbot",
        "email": "example@example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# CORS aktivieren (konfigurierbar über ALLOWED_ORIGINS Umgebungsvariable)
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in allowed_origins.split(",")] if allowed_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Globale Fehlerbehandlung
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Behandelt Validierungsfehler und gibt eine strukturierte Fehlermeldung zurück.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validierungsfehler",
            "details": exc.errors(),
            "data": None
        },
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Behandelt HTTP-Ausnahmen und gibt eine strukturierte Fehlermeldung zurück.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "details": None,
            "data": None
        },
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Behandelt allgemeine Ausnahmen und gibt eine strukturierte Fehlermeldung zurück.
    """
    logger.error(f"Unbehandelte Ausnahme: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Ein interner Serverfehler ist aufgetreten",
            "details": str(exc) if app.debug else None,
            "data": None
        },
    )

# In-memory stores (can be replaced with DB later)
CUSTOMERS: Dict[str, dict] = {}
INVOICES: Dict[str, dict] = {}

# BilBot message store
MESSAGES: Dict[str, dict] = {}

# Load messages from JSON file if it exists
MESSAGES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gesammelte_nachrichten.json")
if os.path.exists(MESSAGES_FILE):
    try:
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            messages_data = json.load(f)
            for msg in messages_data:
                # Convert Discord ID to string for consistent key handling
                msg_id = str(msg["id"])
                MESSAGES[msg_id] = msg
        logger.info(f"Loaded {len(MESSAGES)} messages from {MESSAGES_FILE}")
    except Exception as e:
        logger.error(f"Error loading messages from {MESSAGES_FILE}: {e}")


class CustomerCreate(BaseModel):
    """
    Modell zur Erstellung eines neuen Kunden.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name des Kunden"
    )
    email: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="E-Mail-Adresse des Kunden"
    )
    address: Optional[str] = Field(
        None,
        max_length=500,
        description="Postanschrift des Kunden (optional)"
    )

class Customer(CustomerCreate):
    """
    Vollständiges Kundenmodell mit ID.
    """
    id: str = Field(
        ...,
        description="Eindeutige ID des Kunden"
    )

class InvoiceCreate(BaseModel):
    """
    Modell zur Erstellung einer neuen Rechnung.
    """
    customer_id: str = Field(
        ...,
        description="ID des Kunden, dem die Rechnung zugeordnet ist"
    )
    amount: float = Field(
        ...,
        ge=0,
        description="Rechnungsbetrag (muss größer oder gleich 0 sein)"
    )
    currency: str = Field(
        "EUR",
        min_length=3,
        max_length=3,
        description="Währungscode nach ISO 4217 (Standard: EUR)"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Beschreibung oder Zweck der Rechnung (optional)"
    )

class Invoice(InvoiceCreate):
    """
    Vollständiges Rechnungsmodell mit ID, Status und Ausstellungsdatum.
    """
    id: str = Field(
        ...,
        description="Eindeutige ID der Rechnung"
    )
    status: str = Field(
        "open",
        description="Status der Rechnung (Standard: 'open')"
    )
    issued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Zeitpunkt der Rechnungserstellung (UTC)"
    )


class MessageCreate(BaseModel):
    """
    Modell zur Erstellung einer neuen Discord-Nachricht.
    """
    autor: str = Field(
        ...,
        description="Name des Nachrichtenautors"
    )
    autor_id: Any = Field(
        ...,
        description="Discord-ID des Autors (kann String oder Integer sein)"
    )
    channel: str = Field(
        ...,
        description="Name des Discord-Kanals"
    )
    channel_id: Any = Field(
        ...,
        description="Discord-ID des Kanals (kann String oder Integer sein)"
    )
    guild: str = Field(
        ...,
        description="Name des Discord-Servers (Guild)"
    )
    guild_id: Any = Field(
        ...,
        description="Discord-ID des Servers (kann String oder Integer sein)"
    )
    inhalt: str = Field(
        ...,
        description="Textinhalt der Nachricht"
    )
    attachments: Optional[List[str]] = Field(
        default_factory=list,
        description="Liste von Anhängen (URLs oder Dateipfade)"
    )

class Message(BaseModel):
    """
    Vollständiges Nachrichtenmodell mit ID, Zeitstempel und Link.
    """
    id: Any = Field(
        ...,
        description="Eindeutige Discord-ID der Nachricht (kann String oder Integer sein)"
    )
    autor: str = Field(
        ...,
        description="Name des Nachrichtenautors"
    )
    autor_id: Any = Field(
        ...,
        description="Discord-ID des Autors"
    )
    channel: str = Field(
        ...,
        description="Name des Discord-Kanals"
    )
    channel_id: Any = Field(
        ...,
        description="Discord-ID des Kanals"
    )
    guild: str = Field(
        ...,
        description="Name des Discord-Servers (Guild)"
    )
    guild_id: Any = Field(
        ...,
        description="Discord-ID des Servers"
    )
    inhalt: str = Field(
        ...,
        description="Textinhalt der Nachricht"
    )
    zeitstempel: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="Zeitstempel der Nachricht im Format 'YYYY-MM-DD HH:MM:SS'"
    )
    attachments: Optional[List[str]] = Field(
        default_factory=list,
        description="Liste von Anhängen (URLs oder Dateipfade)"
    )
    link: Optional[str] = Field(
        None,
        description="Link zur Nachricht in Discord (optional)"
    )
    kategorie: Optional[str] = Field(
        None,
        description="Kategorie der Nachricht (optional)"
    )


@app.get("/health",
    summary="Systemstatus prüfen",
    description="Gibt den aktuellen Systemstatus und Zeitstempel zurück.",
    tags=["system"]
)
def health():
    """
    Überprüft den Systemstatus der API.

    Returns:
        dict: Ein Objekt mit dem Status "ok" und dem aktuellen Zeitstempel
    """
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# Customers CRUD
@app.get(
    "/customers",
    response_model=List[Customer],
    summary="Alle Kunden abrufen",
    description="Gibt eine Liste aller Kunden zurück.",
    tags=["customers"]
)
def list_customers():
    """Ruft alle Kunden aus der Datenbank ab."""
    return list(CUSTOMERS.values())

@app.post(
    "/customers",
    response_model=Customer,
    status_code=status.HTTP_201_CREATED,
    summary="Neuen Kunden erstellen",
    description="Erstellt einen neuen Kunden mit den angegebenen Daten und generiert eine eindeutige ID.",
    tags=["customers"],
    responses={
        201: {"description": "Kunde erfolgreich erstellt"},
        422: {"description": "Validierungsfehler in den Kundendaten"},
        409: {"description": "Ein Kunde mit dieser E-Mail-Adresse existiert bereits"}
    }
)
def create_customer(payload: CustomerCreate):
    """Erstellt einen neuen Kunden in der Datenbank."""
    # Prüfe, ob ein Kunde mit der gleichen E-Mail bereits existiert
    for existing_customer in CUSTOMERS.values():
        if existing_customer["email"] == payload.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ein Kunde mit dieser E-Mail-Adresse existiert bereits"
            )

    cid = uuid4().hex
    customer = {"id": cid, **payload.model_dump()}
    CUSTOMERS[cid] = customer
    logger.info(f"Customer created: {cid}")
    return customer

@app.get(
    "/customers/{customer_id}",
    response_model=Customer,
    summary="Kunden nach ID abrufen",
    description="Gibt einen bestimmten Kunden anhand seiner ID zurück.",
    tags=["customers"]
)
def get_customer(customer_id: str):
    """Ruft einen bestimmten Kunden anhand seiner ID ab."""
    customer = CUSTOMERS.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@app.put(
    "/customers/{customer_id}",
    response_model=Customer,
    summary="Kundendaten aktualisieren",
    description="Aktualisiert die Daten eines bestehenden Kunden.",
    tags=["customers"]
)
def update_customer(customer_id: str, payload: CustomerCreate):
    """Aktualisiert die Daten eines bestehenden Kunden."""
    if customer_id not in CUSTOMERS:
        raise HTTPException(status_code=404, detail="Customer not found")
    updated = {"id": customer_id, **payload.model_dump()}
    CUSTOMERS[customer_id] = updated
    logger.info(f"Customer updated: {customer_id}")
    return updated

@app.delete(
    "/customers/{customer_id}",
    summary="Kunden löschen",
    description="Löscht einen Kunden anhand seiner ID.",
    tags=["customers"],
    responses={
        200: {"description": "Kunde erfolgreich gelöscht"},
        404: {"description": "Kunde nicht gefunden"}
    }
)
def delete_customer(customer_id: str):
    """Löscht einen Kunden aus der Datenbank."""
    if customer_id not in CUSTOMERS:
        raise HTTPException(status_code=404, detail="Customer not found")
    # delete invoices associated
    for inv_id, inv in list(INVOICES.items()):
        if inv.get("customer_id") == customer_id:
            INVOICES.pop(inv_id, None)
    CUSTOMERS.pop(customer_id)
    logger.info(f"Customer deleted: {customer_id}")
    return {"deleted": True}


# Invoices CRUD
@app.get("/invoices", response_model=List[Invoice], tags=["invoices"])
def list_invoices():
    return list(INVOICES.values())

@app.post(
    "/invoices",
    response_model=Invoice,
    status_code=status.HTTP_201_CREATED,
    tags=["invoices"],
    responses={
        201: {"description": "Rechnung erfolgreich erstellt"},
        404: {"description": "Kunde nicht gefunden"},
        422: {"description": "Validierungsfehler in den Rechnungsdaten"}
    }
)
def create_invoice(payload: InvoiceCreate):
    """
    Erstellt eine neue Rechnung.

    Args:
        payload: Die Daten der zu erstellenden Rechnung

    Returns:
        Invoice: Die erstellte Rechnung mit generierter ID

    Raises:
        HTTPException: Wenn der angegebene Kunde nicht existiert oder bei Validierungsfehlern
    """
    # ensure customer exists
    if payload.customer_id not in CUSTOMERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kunde mit der angegebenen ID nicht gefunden"
        )

    # Prüfen, ob der Betrag gültig ist
    if payload.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Der Rechnungsbetrag muss größer als 0 sein"
        )

    iid = uuid4().hex
    invoice = Invoice(id=iid, **payload.model_dump())
    INVOICES[iid] = invoice.model_dump()
    logger.info(f"Invoice created: {iid}")
    return invoice

@app.get("/invoices/{invoice_id}", response_model=Invoice, tags=["invoices"])
def get_invoice(invoice_id: str):
    inv = INVOICES.get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv

@app.put("/invoices/{invoice_id}", response_model=Invoice, tags=["invoices"])
def update_invoice(invoice_id: str, payload: InvoiceCreate, status_value: Optional[str] = None):
    if invoice_id not in INVOICES:
        raise HTTPException(status_code=404, detail="Invoice not found")
    # status can be updated via query param status_value
    base = Invoice(id=invoice_id, **payload.model_dump())
    inv = base.model_dump()
    if status_value:
        inv["status"] = status_value
    INVOICES[invoice_id] = inv
    logger.info(f"Invoice updated: {invoice_id}")
    return inv

@app.delete("/invoices/{invoice_id}", tags=["invoices"])
def delete_invoice(invoice_id: str):
    if invoice_id not in INVOICES:
        raise HTTPException(status_code=404, detail="Invoice not found")
    INVOICES.pop(invoice_id)
    logger.info(f"Invoice deleted: {invoice_id}")
    return {"deleted": True}


# BilBot Messages CRUD
@app.get(
    "/messages",
    response_model=List[Message],
    summary="Alle Discord-Nachrichten abrufen",
    description="Gibt eine paginierte Liste aller vom BilBot gesammelten Discord-Nachrichten zurück. Diese Funktion ermöglicht den Zugriff auf den vollständigen Nachrichtenverlauf mit effizienter Paginierung.",
    tags=["messages"],
    responses={
        200: {"description": "Liste der Discord-Nachrichten"},
        422: {"description": "Validierungsfehler bei den Paginierungsparametern"}
    }
)
def list_messages(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    """
    Ruft alle gespeicherten Discord-Nachrichten ab.

    Diese Funktion ermöglicht den Zugriff auf den vollständigen Nachrichtenverlauf,
    der vom BilBot aus Discord-Kanälen gesammelt wurde. Die Ergebnisse können
    durch Paginierungsparameter eingeschränkt werden, um große Datenmengen
    effizient zu verarbeiten.

    Args:
        limit: Maximale Anzahl der zurückzugebenden Einträge
        offset: Anzahl der zu überspringenden Einträge (für Paginierung)

    Returns:
        List[Message]: Liste der Nachrichten, sortiert nach Zeitstempel (neueste zuerst)

    Beispiel:
        GET /messages?offset=100&limit=50
    """
    messages = list(MESSAGES.values())
    # Sort by timestamp (newest first)
    messages.sort(key=lambda x: x.get("zeitstempel", ""), reverse=True)
    return messages[offset:offset+limit]

@app.post(
    "/messages",
    response_model=Message,
    status_code=status.HTTP_201_CREATED,
    summary="Neue Nachricht erstellen",
    description="Erstellt eine neue Discord-Nachricht mit den angegebenen Daten.",
    tags=["messages"]
)
def create_message(payload: MessageCreate):
    """
    Erstellt eine neue Discord-Nachricht.

    Args:
        payload: Die Daten der zu erstellenden Nachricht

    Returns:
        Message: Die erstellte Nachricht mit generierter ID und Zeitstempel
    """
    # Generate a unique ID (similar to Discord's snowflake IDs)
    msg_id = str(uuid4().int)

    # Create message with timestamp
    message = Message(
        id=msg_id,
        **payload.model_dump()
    )

    # Store in memory
    MESSAGES[msg_id] = message.model_dump()
    logger.info(f"Nachricht erstellt: {msg_id}")
    return message

@app.get(
    "/messages/search",
    response_model=List[Message],
    summary="Discord-Nachrichten durchsuchen",
    description="Durchsucht alle Discord-Nachrichten nach einem Suchbegriff im Inhalt, mit optionalen Filtern für Kanal und Autor. Diese Funktion ermöglicht das Auffinden spezifischer Konversationen im Discord-Verlauf.",
    tags=["messages"],
    responses={
        200: {"description": "Suchergebnisse (kann leer sein)"},
        422: {"description": "Validierungsfehler (z.B. Suchbegriff zu kurz)"}
    }
)
def search_messages(
    q: str = Query(..., min_length=1, description="Suchbegriff für Discord-Nachrichten"),
    channel: Optional[str] = Query(None, description="Optionaler Filter für Discord-Kanal"),
    author: Optional[str] = Query(None, description="Optionaler Filter für Discord-Autor"),
    limit: int = Query(20, ge=1, le=50, description="Maximale Anzahl der Ergebnisse")
):
    """
    Durchsucht alle Discord-Nachrichten nach einem Suchbegriff mit optionaler Filterung.

    Diese Funktion ermöglicht das Durchsuchen aller vom BilBot gesammelten Discord-Nachrichten
    nach einem bestimmten Suchbegriff. Die Suche kann durch Angabe eines spezifischen Kanals
    oder Autors weiter eingeschränkt werden.

    Args:
        q: Der Suchbegriff, der in den Nachrichteninhalten gesucht wird
        channel: Optionaler Filter für den Discord-Kanalnamen
        author: Optionaler Filter für den Discord-Autornamen
        limit: Maximale Anzahl der zurückzugebenden Ergebnisse

    Returns:
        List[Message]: Liste der gefundenen Discord-Nachrichten (kann leer sein)

    Beispiel:
        GET /messages/search?q=hilfe&channel=allgemein&limit=10
    """
    results = []

    for msg in MESSAGES.values():
        # Check if message content contains search query (case insensitive)
        if q.lower() not in msg.get("inhalt", "").lower():
            continue

        # Apply optional filters
        if channel and msg.get("channel", "").lower() != channel.lower():
            continue

        if author and msg.get("autor", "").lower() != author.lower():
            continue

        results.append(msg)

        # Limit results
        if len(results) >= limit:
            break

    # Leere Liste zurückgeben, wenn keine Ergebnisse gefunden wurden
    return results

@app.get(
    "/messages/stats",
    summary="Discord-Nachrichtenstatistiken abrufen",
    description="Gibt umfassende Statistiken über die vom BilBot gesammelten Discord-Nachrichten zurück, einschließlich Gesamtzahl, Top-Autoren, Top-Kanäle und zeitliche Verteilung für Analysen und Visualisierungen.",
    tags=["messages"],
    responses={
        200: {"description": "Detaillierte Discord-Nachrichtenstatistiken"}
    }
)
def get_message_stats():
    """
    Generiert umfassende Statistiken über die gesammelten Discord-Nachrichten.

    Diese Funktion analysiert alle vom BilBot gesammelten Discord-Nachrichten und
    erstellt verschiedene statistische Auswertungen, die für Analysen und Visualisierungen
    verwendet werden können. Die Statistiken umfassen die Gesamtzahl der Nachrichten,
    die aktivsten Kanäle und Autoren sowie eine zeitliche Verteilung der Nachrichten.

    Returns:
        dict: Ein Objekt mit folgenden Statistiken:
            - total_messages: Gesamtzahl der gesammelten Discord-Nachrichten
            - channels: Die 5 aktivsten Discord-Kanäle mit Nachrichtenanzahl
            - authors: Die 5 aktivsten Discord-Autoren mit Nachrichtenanzahl
            - messages_per_day: Zeitliche Verteilung der Nachrichten nach Datum

    Beispiel-Antwort:
        {
            "total_messages": 1250,
            "channels": [
                {"name": "allgemein", "count": 450},
                {"name": "hilfe", "count": 320}
            ],
            "authors": [
                {"name": "User1", "count": 120},
                {"name": "User2", "count": 95}
            ],
            "messages_per_day": [
                {"date": "2023-05-01", "count": 45},
                {"date": "2023-05-02", "count": 52}
            ]
        }
    """
    if not MESSAGES:
        return {
            "total_messages": 0,
            "channels": {},
            "authors": {},
            "messages_per_day": {}
        }

    # Initialize stats
    channels = {}
    authors = {}
    messages_per_day = {}

    # Process messages
    for msg in MESSAGES.values():
        # Count by channel
        channel = msg.get("channel", "unknown")
        channels[channel] = channels.get(channel, 0) + 1

        # Count by author
        author = msg.get("autor", "unknown")
        authors[author] = authors.get(author, 0) + 1

        # Count by day
        try:
            date = msg.get("zeitstempel", "").split(" ")[0]
            messages_per_day[date] = messages_per_day.get(date, 0) + 1
        except (IndexError, AttributeError):
            pass

    # Sort results
    top_channels = dict(sorted(channels.items(), key=lambda x: x[1], reverse=True)[:5])
    top_authors = dict(sorted(authors.items(), key=lambda x: x[1], reverse=True)[:5])

    return {
        "total_messages": len(MESSAGES),
        "channels": top_channels,
        "authors": top_authors,
        "messages_per_day": dict(sorted(messages_per_day.items())[-30:])  # Last 30 days
    }

@app.get(
    "/messages/{message_id}",
    response_model=Message,
    summary="Nachricht nach ID abrufen",
    description="Gibt eine bestimmte Discord-Nachricht anhand ihrer ID zurück.",
    tags=["messages"],
    responses={
        200: {"description": "Nachricht gefunden"},
        404: {"description": "Nachricht nicht gefunden"}
    }
)
def get_message(message_id: int):
    """
    Ruft eine bestimmte Discord-Nachricht anhand ihrer ID ab.

    Args:
        message_id: Die ID der gesuchten Nachricht

    Returns:
        Message: Die gefundene Nachricht

    Raises:
        HTTPException: Wenn keine Nachricht mit der angegebenen ID gefunden wurde
    """
    message = MESSAGES.get(str(message_id))
    if not message:
        raise HTTPException(status_code=404, detail="Nachricht nicht gefunden")
    return message

@app.get(
    "/messages/export",
    summary="Nachrichten exportieren",
    description="Exportiert Nachrichten im JSON-Format mit optionalen Filtern.",
    tags=["messages"],
    responses={
        200: {"description": "Exportierte Nachrichten im JSON-Format"}
    }
)
def export_messages(
    channel: Optional[str] = None,
    author: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    search_term: Optional[str] = None
):
    """
    Exportiert Nachrichten im JSON-Format mit optionalen Filtern.

    Args:
        channel: Optionaler Filter für den Discord-Kanalnamen
        author: Optionaler Filter für den Discord-Autornamen
        start_date: Optionaler Filter für das Startdatum (Format: YYYY-MM-DD)
        end_date: Optionaler Filter für das Enddatum (Format: YYYY-MM-DD)
        category: Optionaler Filter für die Nachrichtenkategorie
        search_term: Optionaler Suchbegriff im Nachrichteninhalt

    Returns:
        List[Message]: Liste der gefilterten Nachrichten im JSON-Format
    """
    results = []

    for msg in MESSAGES.values():
        # Anwenden der optionalen Filter
        if channel and msg.get("channel", "").lower() != channel.lower():
            continue

        if author and msg.get("autor", "").lower() != author.lower():
            continue

        if category and msg.get("kategorie", "").lower() != category.lower():
            continue

        if search_term and search_term.lower() not in msg.get("inhalt", "").lower():
            continue

        # Datumsfilter anwenden
        if start_date or end_date:
            try:
                msg_date = msg.get("zeitstempel", "").split(" ")[0]

                if start_date and msg_date < start_date:
                    continue

                if end_date and msg_date > end_date:
                    continue
            except (IndexError, AttributeError):
                continue

        results.append(msg)

    return results

@app.get(
    "/messages/filter",
    summary="Erweiterte Nachrichtenfilterung",
    description="Filtert Nachrichten nach verschiedenen Kriterien wie Zeitraum, Kategorie und Suchbegriff.",
    tags=["messages"],
    responses={
        200: {"description": "Gefilterte Nachrichten"}
    }
)
def filter_messages(
    channel: Optional[str] = None,
    author: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    search_term: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Filtert Nachrichten nach verschiedenen Kriterien mit Paginierung.

    Args:
        channel: Optionaler Filter für den Discord-Kanalnamen
        author: Optionaler Filter für den Discord-Autornamen
        start_date: Optionaler Filter für das Startdatum (Format: YYYY-MM-DD)
        end_date: Optionaler Filter für das Enddatum (Format: YYYY-MM-DD)
        category: Optionaler Filter für die Nachrichtenkategorie
        search_term: Optionaler Suchbegriff im Nachrichteninhalt
        limit: Maximale Anzahl der zurückzugebenden Ergebnisse (1-100)
        offset: Anzahl der zu überspringenden Ergebnisse für Paginierung

    Returns:
        dict: Ein Objekt mit den gefilterten Nachrichten und Metadaten zur Paginierung
    """
    results = []

    for msg in MESSAGES.values():
        # Anwenden der optionalen Filter
        if channel and msg.get("channel", "").lower() != channel.lower():
            continue

        if author and msg.get("autor", "").lower() != author.lower():
            continue

        if category and msg.get("kategorie", "").lower() != category.lower():
            continue

        if search_term and search_term.lower() not in msg.get("inhalt", "").lower():
            continue

        # Datumsfilter anwenden
        if start_date or end_date:
            try:
                msg_date = msg.get("zeitstempel", "").split(" ")[0]

                if start_date and msg_date < start_date:
                    continue

                if end_date and msg_date > end_date:
                    continue
            except (IndexError, AttributeError):
                continue

        results.append(msg)

    # Sortieren nach Zeitstempel (neueste zuerst)
    results.sort(key=lambda x: x.get("zeitstempel", ""), reverse=True)

    # Paginierung anwenden
    paginated_results = results[offset:offset + limit]

    return {
        "messages": paginated_results,
        "total": len(results),
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < len(results)
    }



# Aktiviert PrefixStripper, um /api Präfix zu entfernen (z.B. von Firebase Hosting Rewrite)
app = PrefixStripper(app, "/api")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
