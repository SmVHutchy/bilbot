// Konfiguration
// Erweiterte Erkennung für lokale Umgebungen (localhost, 127.0.0.1, ::1) und file://
const API_BASE_URL = (
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1' ||
  window.location.hostname === '::1' ||
  window.location.protocol === 'file:'
) ? 'http://localhost:8000' : '/api';
let currentPage = 1;
const pageSize = 20;

// DOM-Elemente
document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    const filterButtons = document.querySelectorAll('.filter-button');
    const sections = document.querySelectorAll('.section');

    // Aktuelle Zeit anzeigen
    function updateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        document.getElementById('current-time').textContent = timeString + ' CET';
    }
    updateTime();
    setInterval(updateTime, 60000);

    // Nachrichten-Sektion
    const messagesList = document.getElementById('messages-list');
    const refreshButton = document.getElementById('refresh-messages');
    const prevPageButton = document.getElementById('prev-page');
    const nextPageButton = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');

    // Such-Sektion
    const searchButton = document.getElementById('search-button');
    const searchQuery = document.getElementById('search-query');
    const searchChannel = document.getElementById('search-channel');
    const searchAuthor = document.getElementById('search-author');
    const searchLimit = document.getElementById('search-limit');
    const searchResultsList = document.getElementById('search-results-list');

    // Statistik-Sektion
    const totalMessagesElement = document.getElementById('total-messages');
    const channelsChart = document.getElementById('channels-chart');
    const authorsChart = document.getElementById('authors-chart');
    const timeChart = document.getElementById('time-chart');

    // Event-Listener für Navigation
    filterButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const targetSection = this.getAttribute('data-section');

            // Aktiven Button aktualisieren
            filterButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');

            // Aktive Sektion anzeigen
            sections.forEach(section => {
                section.classList.remove('active');
                if (section.id === targetSection) {
                    section.classList.add('active');

                    // Daten laden, wenn die Sektion aktiviert wird
                    if (targetSection === 'messages') {
                        loadMessages();
                    } else if (targetSection === 'stats') {
                        loadStats();
                    }
                }
            });
        });
    });

    // Detailansicht für Nachrichten
    function setupMessageDetailView() {
        const modal = document.getElementById('message-detail-modal');
        const closeModal = document.querySelector('.close-modal');

        // Schließen-Button
        closeModal.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        // Schließen bei Klick außerhalb des Modals
        window.addEventListener('click', (event) => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    }

    setupMessageDetailView();

    // Refresh-Button
    refreshButton.addEventListener('click', () => {
        loadMessages();
    });

    // Pagination-Buttons
    prevPageButton.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadMessages();
        }
    });

    nextPageButton.addEventListener('click', () => {
        currentPage++;
        loadMessages();
    });

    // Suche
    searchButton.addEventListener('click', () => {
        if (searchQuery.value.trim()) {
            searchMessages();
        }
    });

    // Initial Nachrichten laden
    loadMessages();
});

// API-Funktionen
async function fetchAPI(endpoint, params = {}) {
    // Robuste URL-Konstruktion: relative /api-Basis zu absoluter Origin auflösen
    const base = API_BASE_URL.startsWith('http')
        ? API_BASE_URL
        : `${window.location.origin}${API_BASE_URL}`;

    // Endpunkt mit Basis korrekt verketten
    const urlWithoutQuery = `${base}${endpoint}`;

    // Query-String aufbauen (nur valide Werte)
    const searchParams = new URLSearchParams();
    Object.keys(params).forEach(key => {
        const val = params[key];
        if (val !== null && val !== undefined && val !== '') {
            searchParams.append(key, val);
        }
    });

    const fullUrl = searchParams.toString()
        ? `${urlWithoutQuery}?${searchParams.toString()}`
        : urlWithoutQuery;

    try {
        const response = await fetch(fullUrl);

        if (!response.ok) {
            throw new Error(`API-Fehler: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Fehler beim API-Aufruf:', error);
        return null;
    }
}

// Nachrichten laden
async function loadMessages() {
    const messagesList = document.getElementById('messages-list');
    const prevPageButton = document.getElementById('prev-page');
    const nextPageButton = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');

    messagesList.innerHTML = '<p class="loading">Nachrichten werden geladen...</p>';

    const offset = (currentPage - 1) * pageSize;
    const messages = await fetchAPI('/messages', {
        limit: pageSize,
        offset: offset
    });

    if (!messages || messages.length === 0) {
        messagesList.innerHTML = '<p class="empty-state">Keine Nachrichten gefunden.</p>';
        nextPageButton.disabled = true;
    } else {
        renderMessages(messagesList, messages);
        nextPageButton.disabled = messages.length < pageSize;
    }

    prevPageButton.disabled = currentPage === 1;
    pageInfo.textContent = `Seite ${currentPage}`;
}

// Nachrichten suchen
async function searchMessages() {
    const searchQuery = document.getElementById('search-query');
    const searchChannel = document.getElementById('search-channel');
    const searchAuthor = document.getElementById('search-author');
    const searchLimit = document.getElementById('search-limit');
    const searchResultsList = document.getElementById('search-results-list');

    searchResultsList.innerHTML = '<p class="loading">Suche läuft...</p>';

    const params = {
        q: searchQuery.value,
        limit: searchLimit.value
    };

    if (searchChannel.value) params.channel = searchChannel.value;
    if (searchAuthor.value) params.author = searchAuthor.value;

    const results = await fetchAPI('/messages/search', params);

    if (!results || results.length === 0) {
        searchResultsList.innerHTML = '<p class="empty-state">Keine Ergebnisse gefunden.</p>';
    } else {
        renderMessages(searchResultsList, results);
    }
}

// Statistiken laden
async function loadStats() {
    const totalMessagesElement = document.getElementById('total-messages');

    const stats = await fetchAPI('/messages/stats');

    if (!stats) {
        return;
    }

    // Gesamtnachrichten anzeigen
    totalMessagesElement.textContent = stats.total_messages || 0;

    // Datenformate vereinheitlichen (API liefert aktuell Objekte/Dicts)
    const channelsData = Array.isArray(stats.channels)
        ? stats.channels
        : Object.entries(stats.channels || {}).map(([name, count]) => ({ name, count }));

    const authorsData = Array.isArray(stats.authors)
        ? stats.authors
        : Object.entries(stats.authors || {}).map(([name, count]) => ({ name, count }));

    let timeData = Array.isArray(stats.messages_per_day)
        ? stats.messages_per_day
        : Object.entries(stats.messages_per_day || {}).map(([date, count]) => ({ date, count }));

    // Zeitdaten nach Datum sortieren
    timeData = timeData.sort((a, b) => new Date(a.date) - new Date(b.date));

    // Charts erstellen
    createChannelsChart(channelsData);
    createAuthorsChart(authorsData);
    createTimeChart(timeData);
}

// Hilfsfunktionen
function renderMessages(container, messages) {
    container.innerHTML = '';

    messages.forEach(message => {
        const messageCard = document.createElement('div');
        messageCard.className = 'message-card';

        const author = message.author ?? message.autor ?? 'Unbekannt';
        const channel = message.channel ?? message.kanal ?? 'Unbekannt';
        const content = message.content ?? message.inhalt ?? '';
        const timestampRaw = message.timestamp ?? message.zeitstempel ?? '';

        let timestamp = '';
        if (timestampRaw) {
            const tryDate = new Date(timestampRaw);
            if (!isNaN(tryDate)) {
                timestamp = tryDate.toLocaleString('de-DE');
            } else {
                // Fallback: Roh-String anzeigen, falls nicht parsebar
                timestamp = escapeHTML(timestampRaw);
            }
        }

        messageCard.innerHTML = `
            <div class="message-header">
                <span class="author">${escapeHTML(author)}</span>
                <span class="channel">${escapeHTML(channel)}</span>
            </div>
            <div class="message-content">${escapeHTML(content)}</div>
            <div class="timestamp">${timestamp}</div>
        `;

        container.appendChild(messageCard);
    });
}

function createChannelsChart(channels) {
    const ctx = document.getElementById('channels-chart').getContext('2d');

    if (window.channelsChart) {
        window.channelsChart.destroy();
    }

    const labels = channels.map(c => c.name);
    const data = channels.map(c => c.count);

    window.channelsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Nachrichten pro Kanal',
                data: data,
                backgroundColor: '#5865F2',
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function createAuthorsChart(authors) {
    const ctx = document.getElementById('authors-chart').getContext('2d');

    if (window.authorsChart) {
        window.authorsChart.destroy();
    }

    const labels = authors.map(a => a.name);
    const data = authors.map(a => a.count);

    window.authorsChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#5865F2',
                    '#3498DB',
                    '#9B59B6',
                    '#2ECC71',
                    '#F1C40F'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

function createTimeChart(timeData) {
    const ctx = document.getElementById('time-chart').getContext('2d');

    if (window.timeChart) {
        window.timeChart.destroy();
    }

    const labels = timeData.map(d => d.date);
    const data = timeData.map(d => d.count);

    window.timeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Nachrichten pro Tag',
                data: data,
                borderColor: '#5865F2',
                backgroundColor: 'rgba(88, 101, 242, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Sicherheitsfunktion zum Escapen von HTML
function escapeHTML(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
