# VPS deployment

The VPS runs only the public archive, SQLite database and website. The ESP8266,
serial gateway, Rialo CLI wallet, anchor watcher and publisher remain on the
edge computer.

## Layout

- application: `/opt/rialo-edge-log`
- virtual environment: `/opt/rialo-edge-log/.venv`
- database: `/var/lib/rialo-edge-log/archive.sqlite3`
- secret environment: `/etc/rialo-edge-log/archive.env`
- internal listener: `127.0.0.1:8090`
- public entry point: Nginx with HTTPS

## First installation

Install Git, Python, Nginx and Certbot, clone the repository into
`/opt/rialo-edge-log`, create a dedicated system user, and install
`gateway/requirements.txt` into `.venv`. Copy the supplied service and Nginx
templates into their system locations.

Before enabling the services:

1. replace `YOUR_DOMAIN` in `nginx.conf`;
2. generate a long random ingestion token;
3. save it in `/etc/rialo-edge-log/archive.env` with mode `600`;
4. issue a TLS certificate with Certbot;
5. allow only SSH, HTTP and HTTPS through the firewall.

Do not start the Windows publisher against a plain HTTP URL. Its bearer token
must travel only over HTTPS.

## Health and backup

The health endpoint is `GET /api/health`. Back up the SQLite database with its
online backup command instead of copying a live database file:

```bash
sqlite3 /var/lib/rialo-edge-log/archive.sqlite3 \
  ".backup '/var/lib/rialo-edge-log/archive-backup.sqlite3'"
```

The service is intentionally bound to localhost. Nginx is the only public
listener and terminates TLS before forwarding requests to the archive.
