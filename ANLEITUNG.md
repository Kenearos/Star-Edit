# Anleitung: StarCraft-Kampagnen-MCP-Server einrichten & benutzen

Diese Anleitung ist für **null Programmierkenntnisse** gedacht. Du tippst nur die
fettgedruckten Befehle ab. Wenn etwas von *deinem* Setup abhängt, steht ausdrücklich
dabei „**das musst du anpassen**".

---

## 0. Was du brauchst (Checkliste)

- [ ] **Zugang zu deinem Hetzner-VPS** (per SSH – also das schwarze Terminal-Fenster,
      mit dem du dich auf den Server einloggst).
- [ ] Auf dem VPS sind **Docker** und **Caddy** installiert und laufen bereits
      (hast du). Caddy ist dein „Türsteher", der die Webadresse + das Sicherheitsschloss
      (TLS/https) bereitstellt.
- [ ] Eine **Subdomain**, z.B. `sc-mcp.pixel-by-design.de`, deren DNS-Eintrag auf die
      IP-Adresse deines VPS zeigt. (Einstellung beim Anbieter, wo deine Domain liegt.)
- [ ] Ein **Claude-Bezahl-Account** (Pro, Max, Team oder Enterprise). Nur diese können
      eigene „Custom Connectors" hinzufügen – im Gratis-Account fehlt die Funktion.
- [ ] **Basis-Karten** (`.scx`/`.scm`) und optionale **WAV-Sounddateien**, aus denen
      Claude Missionen bauen soll. Eine Beispiel-Karte liegt schon dabei.

> **Begriffe in einem Satz:**
> *MCP-Server* = das Programm, das Karten lesen/schreiben kann.
> *Connector* = die Verbindung, über die Claude dieses Programm benutzt.
> *Docker* = verpackt das Programm so, dass es überall gleich startet.
> *Caddy* = stellt die https-Webadresse bereit.

---

## Teil A — Einmalig einrichten (ca. 15 Minuten)

### A1. Auf den Server einloggen

Öffne ein Terminal auf deinem Computer und logge dich auf dem VPS ein (Adresse/Benutzer
hast du von Hetzner):

```bash
ssh dein-benutzer@deine-server-ip
```

Alle weiteren Befehle tippst du **auf dem Server** (im eingeloggten Fenster).

### A2. Das Projekt auf den Server holen

```bash
git clone https://github.com/Kenearos/Star-Edit.git
cd Star-Edit
```

Falls du das Projekt schon mal geholt hast, hol nur die neueste Version:

```bash
cd Star-Edit
git pull origin main
```

### A3. Das Docker-Netzwerk von Caddy herausfinden — **das musst du anpassen**

Damit Caddy mit unserem Server reden kann, müssen beide im selben Docker-Netzwerk sein.
Zeig dir die vorhandenen Netzwerke an:

```bash
docker network ls
```

Suche den Namen, den **dein Caddy** benutzt (oft `caddy`, manchmal `web`, `proxy` o.ä.).
Trage diesen Namen in die Datei `docker-compose.yml` ein – ganz unten steht:

```yaml
networks:
  web:
    external: true
    name: caddy      # <-- hier den echten Netzwerknamen eintragen
```

Bearbeiten kannst du die Datei z.B. mit dem Editor `nano`:

```bash
nano docker-compose.yml
```

(Ändern, dann mit `Strg+O`, `Enter` speichern und `Strg+X` schließen.)

> Wenn du dir unsicher bist, welches Netzwerk Caddy nutzt:
> `docker inspect <caddy-container-name> | grep -i network` zeigt es an.

### A4. Subdomain auf den Server zeigen lassen (DNS) — **das musst du anpassen**

Beim Anbieter deiner Domain legst du einen **A-Record** an:

| Typ | Name (Host) | Wert (Ziel) |
|-----|-------------|-------------|
| A   | `sc-mcp`    | *die IP-Adresse deines VPS* |

Damit wird `sc-mcp.pixel-by-design.de` auf deinen Server gezeigt. (Kann ein paar Minuten
bis Stunden dauern, bis es überall aktiv ist.)

### A5. Caddy für die Subdomain konfigurieren

Öffne deine bestehende Caddy-Konfiguration (deine `Caddyfile`) und füge diesen Block
hinzu – er steht auch in der mitgelieferten Datei [`Caddyfile`](./Caddyfile):

```caddy
sc-mcp.pixel-by-design.de {
	reverse_proxy sc-mcp:8000
}
```

Das heißt: „Alles, was an `sc-mcp.pixel-by-design.de` ankommt, leite an unseren Server
weiter." Caddy holt das https-Zertifikat automatisch.

Danach Caddy neu laden (je nach deinem Setup einer dieser Befehle):

```bash
docker exec -w /etc/caddy <caddy-container-name> caddy reload
# oder, falls Caddy nicht in Docker läuft:
sudo systemctl reload caddy
```

> Falls du die Subdomain im selben Reverse-Proxy noch nicht hattest: `<caddy-container-name>`
> findest du mit `docker ps` (Spalte NAMES).

### A6. Den Server starten (der eine Befehl)

```bash
./run.sh
```

Das baut beim ersten Mal das Programm (dauert 1–2 Minuten) und startet es. Fertig sieht
so aus, dass kein Fehler erscheint und der Server läuft.

Prüfen, ob er läuft:

```bash
./run.sh logs
```

(Mit `Strg+C` schließt du die Log-Ansicht wieder – der Server läuft weiter.)

**Schnelltest, ob alles greift** (baut testweise eine Mini-Mission):

```bash
./run.sh selftest
```

Wenn am Ende **„SELBSTTEST BESTANDEN"** steht, ist das Fundament in Ordnung.

### A7. In Claude als Connector eintragen

1. Claude öffnen (Web oder App) → **Einstellungen** → **Connectors** (bzw.
   „Connectors verwalten").
2. **Custom Connector hinzufügen** wählen.
3. Als Adresse/URL eintragen:

   ```
   https://sc-mcp.pixel-by-design.de/mcp
   ```

   (Wichtig: das `/mcp` am Ende gehört dazu.)
4. Speichern. Ab jetzt darf Claude im Chat die `sc_`-Werkzeuge benutzen.

---

## Teil B — Eine Mission bauen (so läuft es im Alltag)

### B1. Karten & Sounds bereitstellen

Lege deine Dateien auf dem Server in den Ordner `Star-Edit/data/maps/`:

- Basis-Karten: `.scx` oder `.scm`
- Sounds/Voiceover: `.wav`

Hochladen z.B. vom eigenen Rechner aus (in einem **neuen** Terminal, *nicht* eingeloggt
auf dem Server):

```bash
scp meine-karte.scx funk1.wav dein-benutzer@deine-server-ip:~/Star-Edit/data/maps/
```

Eine Beispiel-Karte (`base-map.scx`) liegt bereits drin – du kannst sofort loslegen.

### B2. Mit Claude im Chat arbeiten

Schreib Claude einfach, was du willst – auf Deutsch. Claude ruft dann selbst die
Werkzeuge auf. Beispiele:

> „Zeig mir die vorhandenen Karten."
> → Claude nutzt `sc_list_maps`.

> „Beschreib mir die Karte `base-map.scx`."
> → Claude nutzt `sc_describe_map` (Größe, Spieler, Locations, Trigger).

> „Erstelle auf `base-map.scx` bei Spielstart eine Texteinblendung ‚Mission 1 – Start'
> und spawne 4 Marines für Spieler 1 an einer neuen Location ‚Basis' in der Kartenmitte.
> Speichere das Ergebnis als `mission1.scx`."
> → Claude legt die Location an (`sc_create_location`), baut den Trigger
> (`sc_add_trigger`) und speichert (`sc_save_map`).

Für **Voiceover/Funksprüche**:

> „Bette `funk1.wav` ein und spiel es bei Sekunde 30 zusammen mit dem Text
> ‚Achtung, Feindkontakt!' ab."
> → Claude nutzt `sc_embed_wav` + `sc_add_trigger` (play_wav + display_text).

### B3. Ergebnis abholen

Die fertige Mission liegt danach in `Star-Edit/data/maps/` (z.B. `mission1.scx`). Auf den
eigenen Rechner herunterladen:

```bash
scp dein-benutzer@deine-server-ip:~/Star-Edit/data/maps/mission1.scx .
```

Diese Datei kannst du in StarCraft laden und spielen.

---

## Teil C — Befehls-Spickzettel (auf dem Server, im Ordner `Star-Edit`)

| Was du willst | Befehl |
|---------------|--------|
| Server starten / neu starten | `./run.sh` |
| Logs ansehen (beenden mit Strg+C) | `./run.sh logs` |
| Selbsttest laufen lassen | `./run.sh selftest` |
| Server stoppen | `./run.sh stop` |
| Neueste Programmversion holen | `git pull origin main` danach `./run.sh` |

---

## Teil D — Wenn etwas klemmt

- **Claude sagt, der Connector ist nicht erreichbar.**
  1. Läuft der Server? `./run.sh logs` ansehen.
  2. Zeigt die Subdomain schon auf den Server? Im Browser `https://sc-mcp.pixel-by-design.de/mcp`
     öffnen – kommt *irgendeine* Antwort (kein „Server nicht gefunden"), passt das Grundsätzliche.
  3. Sind Caddy und der `sc-mcp`-Container im **selben** Docker-Netzwerk (Schritt A3)?

- **„network caddy not found" o.ä. beim Start.**
  Der Netzwerkname in `docker-compose.yml` stimmt nicht mit deinem Caddy-Netzwerk
  überein → Schritt A3 wiederholen (`docker network ls`).

- **Claude findet eine Location/Einheit nicht.**
  Die Fehlermeldung listet die verfügbaren Namen auf – einfach einen davon nehmen oder
  die Location vorher anlegen lassen.

- **Ich will den Server ohne Caddy nur kurz lokal testen.**
  In `docker-compose.yml` die zwei `ports:`-Zeilen einkommentieren (`# ports:` und
  `#   - "8000:8000"`), dann `./run.sh`. Endpunkt: `http://deine-server-ip:8000/mcp`.

---

## Sicherheitshinweis

Der Server hat **kein Passwort**: Wer die URL `https://sc-mcp.pixel-by-design.de/mcp`
kennt, kann ihn benutzen. Für ein privates Werkzeug ist das meist okay – halte die URL
aber für dich. Wenn du später einen Zugriffsschutz möchtest, sag Bescheid, dann bauen wir
einen (z.B. ein Token in Caddy) ein.
