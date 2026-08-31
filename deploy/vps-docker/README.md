# Docker VPS deployment

This deployment runs the public archive beside an existing Caddy container on
the external `node_default` Docker network. It does not publish port 8090 on the
VPS. Caddy is the only public entry point.

## Persistent paths

- database: `/var/lib/rialo-edge-log/archive.sqlite3`
- ingestion secret: `/etc/rialo-edge-log/archive.env`
- application checkout: `/opt/rialo-edge-log`

Create the directories and a random ingestion token:

```bash
install -d -m 700 /etc/rialo-edge-log
mkdir -p /var/lib/rialo-edge-log
chown 10001:10001 /var/lib/rialo-edge-log
chmod 750 /var/lib/rialo-edge-log
printf 'RIALO_EDGE_LOG_INGEST_TOKEN=' > /etc/rialo-edge-log/archive.env
openssl rand -hex 32 >> /etc/rialo-edge-log/archive.env
chmod 600 /etc/rialo-edge-log/archive.env
```

Build and start the archive from the repository root:

```bash
docker compose -f deploy/vps-docker/compose.yml up -d --build
docker inspect rialo-edge-log --format '{{.State.Health.Status}}'
```

Add a Caddy virtual host to the existing Caddyfile source:

```caddy
rialo-edge-log.xyz {
    reverse_proxy rialo-edge-log:8090
}
```

If a different hostname uses a Compose environment variable inside an inline
`configs.content` block, escape `$` as `$$`. Recreate only the Caddy service
after validating the merged Compose configuration. Caddy obtains and renews the
HTTPS certificate after DNS resolves to the VPS.

The publisher on the edge computer uses the HTTPS URL and the same ingestion
token. Never commit the token or send it over plain HTTP.
