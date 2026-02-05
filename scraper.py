#!/usr/bin/env python3
"""
Scraper voor voorjaarsklassiekers 2026 startlijsten.
Gebruikt Playwright (headless browser) om data op te halen van ProCyclingStats.
"""

from playwright.sync_api import sync_playwright
import json
import re
from datetime import datetime
import os
import time

# Configuratie koersen (gesorteerd op datum)
RACES = [
    {'id': 'omloop', 'url': 'https://www.procyclingstats.com/race/omloop-het-nieuwsblad/2026/startlist', 'name': 'Omloop Het Nieuwsblad', 'date': '2026-03-01', 'monument': False},
    {'id': 'kbk', 'url': 'https://www.procyclingstats.com/race/kuurne-brussel-kuurne/2026/startlist', 'name': 'Kuurne-Brussel-Kuurne', 'date': '2026-03-02', 'monument': False},
    {'id': 'strade', 'url': 'https://www.procyclingstats.com/race/strade-bianche/2026/startlist', 'name': 'Strade Bianche', 'date': '2026-03-08', 'monument': False},
    {'id': 'sanremo', 'url': 'https://www.procyclingstats.com/race/milano-sanremo/2026/startlist', 'name': 'Milano-Sanremo', 'date': '2026-03-22', 'monument': True},
    {'id': 'brugge', 'url': 'https://www.procyclingstats.com/race/classic-brugge-de-panne/2026/startlist', 'name': 'Brugge-De Panne', 'date': '2026-03-26', 'monument': False},
    {'id': 'e3', 'url': 'https://www.procyclingstats.com/race/e3-harelbeke/2026/startlist', 'name': 'E3 Saxo Classic', 'date': '2026-03-28', 'monument': False},
    {'id': 'gw', 'url': 'https://www.procyclingstats.com/race/gent-wevelgem/2026/startlist', 'name': 'Gent-Wevelgem', 'date': '2026-03-30', 'monument': False},
    {'id': 'ddv', 'url': 'https://www.procyclingstats.com/race/dwars-door-vlaanderen/2026/startlist', 'name': 'Dwars door Vlaanderen', 'date': '2026-04-02', 'monument': False},
    {'id': 'rvv', 'url': 'https://www.procyclingstats.com/race/ronde-van-vlaanderen/2026/startlist', 'name': 'Ronde van Vlaanderen', 'date': '2026-04-06', 'monument': True},
    {'id': 'schelde', 'url': 'https://www.procyclingstats.com/race/scheldeprijs/2026/startlist', 'name': 'Scheldeprijs', 'date': '2026-04-09', 'monument': False},
    {'id': 'roubaix', 'url': 'https://www.procyclingstats.com/race/paris-roubaix/2026/startlist', 'name': 'Paris-Roubaix', 'date': '2026-04-13', 'monument': True},
    {'id': 'brabantse', 'url': 'https://www.procyclingstats.com/race/brabantse-pijl/2026/startlist', 'name': 'Brabantse Pijl', 'date': '2026-04-16', 'monument': False},
    {'id': 'amstel', 'url': 'https://www.procyclingstats.com/race/amstel-gold-race/2026/startlist', 'name': 'Amstel Gold Race', 'date': '2026-04-20', 'monument': False},
    {'id': 'fleche', 'url': 'https://www.procyclingstats.com/race/la-fleche-wallonne/2026/startlist', 'name': 'La Flèche Wallonne', 'date': '2026-04-23', 'monument': False},
    {'id': 'lbl', 'url': 'https://www.procyclingstats.com/race/liege-bastogne-liege/2026/startlist', 'name': 'Liège-Bastogne-Liège', 'date': '2026-04-27', 'monument': True},
]

def normalize_rider_name(name):
    """Normalize rider name for consistent matching."""
    # Remove time indicators like "1h", "21h", etc.
    name = re.sub(r'\d+[hm]$', '', name).strip()
    # Remove asterisks and other markers
    name = re.sub(r'\*', '', name).strip()
    return name

def fetch_startlist(page, race):
    """Fetch and parse a startlist from ProCyclingStats using Playwright."""
    url = race['url']

    try:
        print(f"  Fetching {race['name']}...")

        # Navigate to page
        page.goto(url, wait_until='networkidle', timeout=60000)

        # Wait a bit for dynamic content
        time.sleep(2)

        # Try to close cookie banner if present
        try:
            cookie_btn = page.locator('text="Opslaan + Sluiten"').first
            if cookie_btn.is_visible(timeout=2000):
                cookie_btn.click()
                time.sleep(1)
        except:
            pass

        # Extract rider links using JavaScript
        riders = page.evaluate('''() => {
            const riders = new Set();
            const links = document.querySelectorAll('a[href*="/rider/"]');

            links.forEach(link => {
                const href = link.getAttribute('href') || '';
                const name = link.textContent.trim();

                // Skip stats/overview links
                if (href.includes('statistics') || href.includes('overview') || href.includes('results')) {
                    return;
                }

                // Skip if in footer
                const footer = link.closest('footer') || link.closest('.footer');
                if (footer) return;

                // Check if it's a valid rider name (has space, starts with uppercase)
                if (name.length > 3 && name.includes(' ') && /^[A-ZÄÖÜÉÈÀÁÍÓÚÑ]/.test(name)) {
                    // Remove time indicators
                    const cleanName = name.replace(/\\d+[hm]$/, '').trim();
                    if (cleanName.length > 3) {
                        riders.add(cleanName);
                    }
                }
            });

            return Array.from(riders);
        }''')

        # Filter out popular riders section (common names that appear in footer)
        popular_riders = ['Tadej Pogačar', 'Wout van Aert', 'Remco Evenepoel', 'Jonas Vingegaard',
                        'Mathieu van der Poel', 'Mads Pedersen', 'Isaac Del Toro', 'Paul Magnier',
                        'Demi Vollering', 'Lotte Kopecky', 'Katarzyna Niewiadoma', 'Pauline Ferrand-Prévot']

        # Only filter these if they appear at the end (likely from footer)
        # Keep them if they're in the actual startlist
        filtered_riders = []
        for rider in riders:
            # Keep all riders that look like startlist entries (LASTNAME Firstname format)
            if rider and len(rider) > 3:
                filtered_riders.append(rider)

        print(f"    Found {len(filtered_riders)} riders")
        if filtered_riders:
            print(f"    Sample: {filtered_riders[:5]}")

        return filtered_riders

    except Exception as e:
        print(f"    Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def build_rider_data(races_data):
    """Build a dictionary of rider participations."""
    rider_participations = {}

    for race_id, riders in races_data.items():
        for rider in riders:
            if rider not in rider_participations:
                rider_participations[rider] = []
            rider_participations[rider].append(race_id)

    return rider_participations

def generate_html(rider_data, races, last_update):
    """Generate the HTML page with rider data."""

    races_json = json.dumps(races, ensure_ascii=False)
    rider_data_json = json.dumps(rider_data, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voorjaarsklassiekers 2026 - Deelnames per Renner</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1800px; margin: 0 auto; }}
        h1 {{ text-align: center; margin-bottom: 10px; color: #ffd700; font-size: 2em; }}
        .subtitle {{ text-align: center; color: #888; margin-bottom: 20px; font-size: 0.9em; }}
        .last-update {{ text-align: center; color: #666; margin-bottom: 20px; font-size: 0.8em; }}
        .filters {{
            display: flex; gap: 15px; margin-bottom: 20px;
            flex-wrap: wrap; justify-content: center; align-items: center;
        }}
        .filters input, .filters select {{
            padding: 10px 15px; border: 1px solid #333; border-radius: 8px;
            background: #1a1a2e; color: #eee; font-size: 14px;
        }}
        .filters input:focus, .filters select:focus {{ outline: none; border-color: #ffd700; }}
        .stats {{
            display: flex; gap: 20px; justify-content: center;
            margin-bottom: 20px; flex-wrap: wrap;
        }}
        .stat-box {{
            background: rgba(255,255,255,0.05); padding: 15px 25px;
            border-radius: 10px; text-align: center;
        }}
        .stat-box .number {{ font-size: 2em; font-weight: bold; color: #ffd700; }}
        .stat-box .label {{ font-size: 0.8em; color: #888; }}
        .table-container {{
            overflow-x: auto; background: rgba(255,255,255,0.02);
            border-radius: 12px; padding: 10px;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th, td {{ padding: 10px 8px; text-align: center; border-bottom: 1px solid #333; }}
        th {{
            background: #1a1a2e; color: #ffd700; font-weight: 600;
            cursor: pointer; position: sticky; top: 0; white-space: nowrap;
        }}
        th:hover {{ background: #252545; }}
        th.sortable::after {{ content: ' ↕'; opacity: 0.3; }}
        th.sort-asc::after {{ content: ' ↑'; opacity: 1; }}
        th.sort-desc::after {{ content: ' ↓'; opacity: 1; }}
        td.rider-name {{
            text-align: left; font-weight: 500; white-space: nowrap;
            position: sticky; left: 0; background: #16213e;
        }}
        td.total {{ font-weight: bold; color: #ffd700; background: rgba(255,215,0,0.1); }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        tr:hover td.rider-name {{ background: #1e2d4a; }}
        .check {{ color: #4caf50; font-weight: bold; }}
        .cross {{ color: #333; }}
        .race-header {{
            writing-mode: vertical-rl; text-orientation: mixed;
            transform: rotate(180deg); max-height: 120px; font-size: 11px;
        }}
        .race-date {{ font-size: 9px; color: #888; display: block; }}
        .monument {{ color: #ff6b6b !important; }}
        .legend {{
            display: flex; gap: 20px; justify-content: center;
            margin-top: 20px; font-size: 0.85em; color: #888;
        }}
        .legend span {{ display: flex; align-items: center; gap: 5px; }}
        @media (max-width: 768px) {{
            .race-header {{ font-size: 9px; max-height: 80px; }}
            th, td {{ padding: 6px 4px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Voorjaarsklassiekers 2026</h1>
        <p class="subtitle">Overzicht deelnames wielrenners aan de belangrijkste voorjaarskoersen</p>
        <p class="last-update">Laatste update: {last_update} | Bron: ProCyclingStats (voorlopige startlijsten)</p>

        <div class="stats">
            <div class="stat-box">
                <div class="number" id="totalRiders">0</div>
                <div class="label">Renners</div>
            </div>
            <div class="stat-box">
                <div class="number">15</div>
                <div class="label">Koersen</div>
            </div>
            <div class="stat-box">
                <div class="number" id="maxParticipations">0</div>
                <div class="label">Max deelnames</div>
            </div>
        </div>

        <div class="filters">
            <input type="text" id="searchInput" placeholder="Zoek renner..." onkeyup="filterTable()">
            <select id="minRaces" onchange="filterTable()">
                <option value="1">Min. 1 koers</option>
                <option value="3">Min. 3 koersen</option>
                <option value="5">Min. 5 koersen</option>
                <option value="8">Min. 8 koersen</option>
                <option value="10">Min. 10 koersen</option>
            </select>
        </div>

        <div class="table-container">
            <table id="raceTable">
                <thead>
                    <tr id="headerRow">
                        <th class="sortable" onclick="sortTable(0)">Renner</th>
                        <th class="sortable" onclick="sortTable(1)">Totaal</th>
                    </tr>
                </thead>
                <tbody id="tableBody"></tbody>
            </table>
        </div>

        <div class="legend">
            <span><span class="check">✓</span> = Deelname</span>
            <span><span style="color:#ff6b6b">●</span> = Monument</span>
        </div>
    </div>

    <script>
        const races = {races_json};
        const riderData = {rider_data_json};

        function formatDate(dateStr) {{
            const date = new Date(dateStr);
            const day = date.getDate();
            const month = date.toLocaleDateString('nl-NL', {{ month: 'short' }});
            return `${{day}} ${{month}}`;
        }}

        function buildHeaders() {{
            const headerRow = document.getElementById('headerRow');
            races.forEach((race, index) => {{
                const th = document.createElement('th');
                th.className = 'sortable';
                th.onclick = () => sortTable(index + 2);
                th.innerHTML = `<div class="race-header ${{race.monument ? 'monument' : ''}}">${{race.name}}<span class="race-date">${{formatDate(race.date)}}</span></div>`;
                headerRow.appendChild(th);
            }});
        }}

        function buildTable() {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';

            const riders = Object.entries(riderData).map(([name, participations]) => ({{
                name, participations, total: participations.length
            }})).filter(r => r.total > 0);

            riders.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));

            document.getElementById('totalRiders').textContent = riders.length;
            document.getElementById('maxParticipations').textContent = Math.max(...riders.map(r => r.total), 0);

            riders.forEach(rider => {{
                const tr = document.createElement('tr');
                tr.dataset.total = rider.total;
                tr.dataset.name = rider.name.toLowerCase();

                const tdName = document.createElement('td');
                tdName.className = 'rider-name';
                tdName.textContent = rider.name;
                tr.appendChild(tdName);

                const tdTotal = document.createElement('td');
                tdTotal.className = 'total';
                tdTotal.textContent = rider.total;
                tr.appendChild(tdTotal);

                races.forEach(race => {{
                    const td = document.createElement('td');
                    td.innerHTML = rider.participations.includes(race.id)
                        ? '<span class="check">✓</span>'
                        : '<span class="cross">-</span>';
                    tr.appendChild(td);
                }});

                tbody.appendChild(tr);
            }});
        }}

        function filterTable() {{
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const minRaces = parseInt(document.getElementById('minRaces').value);
            document.querySelectorAll('#tableBody tr').forEach(row => {{
                const name = row.dataset.name;
                const total = parseInt(row.dataset.total);
                row.style.display = (name.includes(searchTerm) && total >= minRaces) ? '' : 'none';
            }});
        }}

        let currentSort = {{ column: 1, direction: 'desc' }};
        function sortTable(columnIndex) {{
            const tbody = document.getElementById('tableBody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const headers = document.querySelectorAll('th');

            let direction = (currentSort.column === columnIndex && currentSort.direction === 'desc') ? 'asc' : 'desc';
            currentSort = {{ column: columnIndex, direction }};

            headers.forEach((h, i) => {{
                h.classList.remove('sort-asc', 'sort-desc');
                if (i === columnIndex) h.classList.add(direction === 'asc' ? 'sort-asc' : 'sort-desc');
            }});

            rows.sort((a, b) => {{
                let aVal, bVal;
                if (columnIndex === 0) {{
                    aVal = a.cells[0].textContent;
                    bVal = b.cells[0].textContent;
                    return direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                }} else if (columnIndex === 1) {{
                    aVal = parseInt(a.cells[1].textContent);
                    bVal = parseInt(b.cells[1].textContent);
                }} else {{
                    aVal = a.cells[columnIndex].textContent === '✓' ? 1 : 0;
                    bVal = b.cells[columnIndex].textContent === '✓' ? 1 : 0;
                }}
                return direction === 'asc' ? aVal - bVal : bVal - aVal;
            }});

            rows.forEach(row => tbody.appendChild(row));
        }}

        document.addEventListener('DOMContentLoaded', () => {{ buildHeaders(); buildTable(); }});
    </script>
</body>
</html>'''

    return html

def main():
    print(f"=== Voorjaarsklassiekers 2026 Scraper (Playwright) ===")
    print(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    with sync_playwright() as p:
        # Launch browser
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        # Fetch all startlists
        races_data = {}
        for race in RACES:
            riders = fetch_startlist(page, race)
            races_data[race['id']] = riders
            time.sleep(1)  # Be nice to the server

        browser.close()

    # Build rider participation data
    rider_data = build_rider_data(races_data)

    total_riders = len(rider_data)
    total_participations = sum(len(p) for p in rider_data.values())

    print()
    print(f"=" * 40)
    print(f"Total unique riders: {total_riders}")
    print(f"Total participations: {total_participations}")
    print(f"=" * 40)

    # Prepare races info for JSON
    races_info = [{'id': r['id'], 'name': r['name'], 'date': r['date'], 'monument': r['monument']} for r in RACES]

    # Generate HTML
    last_update = datetime.now().strftime('%d-%m-%Y %H:%M UTC')
    html = generate_html(rider_data, races_info, last_update)

    # Write to file
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\nHTML file generated: {output_path}")
    print("Done!")

if __name__ == '__main__':
    main()
