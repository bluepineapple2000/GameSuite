# Game Suite

Two Django games share a server-only AI adapter:

- `/couplesQuestions/`: open-ended questions to support conversation and connection. Choose any category, take turns answering out loud, and skip freely. Answers are never submitted or recorded.
- `/imposterGame/`: create or join an invitation-code room with 3–20 players. The host selects a free-text category and starts rounds; players receive their own role. Host control transfers when the host leaves.

## AI and history

The browser talks only to Django. Django calls `AI_BASE_URL` using the configured model. The default is Ollama at `http://ai.np.fruck.name:11434`, model `gemma3:1b`; ensure that model is installed. There is no public proxy endpoint to Ollama. Categories cannot change the endpoint, model, headers or request options. Redirects and environment-based HTTP proxies are disabled. Responses have time, size, type and length limits and are always escaped when displayed.

The SQLite database **is the persistent history file**. Each room has its own `UsedWord` rows and a normalized uniqueness constraint. All prior words are included in every prompt, across category changes and container restarts. The application rejects exact normalized repeats and retries up to three times. Semantic synonyms are not guaranteed unique. An existing room's current word is preserved by the migration; older rounds played before this change cannot be reconstructed.

A room is a game session. History lasts until the last player leaves and the room is deleted; create a new room for a fresh history. To bound prompts, rooms stop after 200 words, and couples sessions stop after 50 questions. History is never silently truncated. Couples history is stored in Django's database sessions, expires after 24 hours of inactivity, and can be cleared with “New session.”

A database lease permits one generation at a time across both games, with a five-second cooldown. Busy requests fail promptly. Provider failures preserve the current round and never expose backend diagnostics. This small-instance configuration uses SQLite and an in-memory Channels layer: run **one Uvicorn process / one replica**. Horizontal scaling needs a shared database, Redis Channels, and revised concurrency controls.

## Container deployment with Ansible

Build with `docker build -f Containerfile -t game-suite .` (or Podman). The container runs as UID/GID `10001:10001` and listens on port 8000. It applies migrations on startup and serves local static files; no browser CDN, fonts, telemetry or third-party scripts are required.

Inject environment values from [.env.example](.env.example) through Ansible. Supply `DJANGO_SECRET_KEY` and `AI_API_KEY` from Vault or another secret store, use `no_log: true` for tasks containing secrets, and restrict any generated environment file to mode `0600`. Generate a new Django secret; the old committed secret is no longer used. Do not use the sample value.

Provision a persistent directory owned by `10001:10001`, mode `0700`, and mount it at `/data`. Container startup sets `umask 077`. Back up the SQLite database consistently before upgrades. The image build excludes local databases, environment files, Git metadata and the scratch Ollama script.

Example runtime shape (adapt image, host path and engine in Ansible):

```sh
docker run --name game-suite \
  --env-file /etc/game-suite/environment \
  --publish 127.0.0.1:8000:8000 \
  --mount type=bind,src=/srv/game-suite/data,dst=/data \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --memory 512m --cpus 1 --pids-limit 128 \
  game-suite
```

Put a TLS reverse proxy in front of this loopback listener. [deploy/nginx.conf.example](deploy/nginx.conf.example) includes HTTP/WebSocket forwarding and per-IP request/connection limits. Review and adapt certificate paths and domains. When `DJANGO_TRUST_PROXY=true`, only this trusted proxy may reach Uvicorn, and it must overwrite forwarded protocol headers. For a proxy on another host, bind only to a private interface and firewall it accordingly. Limit logging and retention: proxy request URLs include room invitation codes. Do not log request bodies, cookies, AI prompts, or authorization headers.

Keep Ollama blocked from the internet. Permit backend egress only to its configured AI host/port and required DNS; the browser needs no route to Ollama. Plain HTTP on that private hop is **not encrypted**: use HTTPS or an encrypted private tunnel if that network is not trusted. HTTPS certificate validation is enabled for configured HTTPS endpoints. Changing the provider to an external service also sends the category and history to that service; review its privacy policy first.

To replace the backend with a Chat Completions compatible API, set:

```text
AI_PROVIDER=openai
AI_BASE_URL=https://your-provider.example/v1
AI_MODEL=your-model
AI_API_KEY=your-secret
```

The compatible provider must support JSON-object responses. `AI_PROVIDER=ollama` instead uses the native `/api/chat` API with a JSON schema. `AI_LANGUAGE` defaults to German. These settings are server-side only.

## Public deployment security and retention

Production defaults disable debugging, require a runtime secret, redirect HTTP to HTTPS, use secure HTTP-only session cookies, protect POST actions with CSRF, validate WebSocket origins and membership, and set a restrictive Content Security Policy. Only the host can start rounds or remove members. Group messages contain only a refresh event, never words or roles. Room pages are not cacheable. Treat room invitation codes like shared secrets; this is an anonymous party game, without verified identities or private-user accounts. If access must be limited to known people, protect the whole site with identity-aware access at the proxy, including WebSockets.

No implementation can promise “no leaks” or a universal highest security standard. These controls still require maintained dependencies, patched hosts, restricted network access, protected backups, rate limiting, and a review of the actual deployed configuration. Anonymous public users can consume the site's allowed generation capacity; use authenticated access if that is unacceptable.

Run `python manage.py clearsessions` daily to purge expired couples sessions. Abandoned imposter rooms and their player names, categories and history remain in SQLite if players never leave; set an operational retention policy and delete abandoned rooms/players through Django administration tooling or a scheduled management command before a public deployment. Database files and backups must never be web-served and should be encrypted at rest where appropriate. No answers from couples conversations are stored.

## Development and verification

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=true
python mySite/manage.py migrate
python mySite/manage.py runserver
```

For live WebSocket support, use `cd mySite && uvicorn mySite.asgi:application --host 127.0.0.1 --port 8000 --no-access-log`. Development mode permits HTTP; never enable it on the public deployment. If no development secret is supplied, one is generated at process startup, so use a fixed local secret if sessions need to survive restarts.

```sh
DJANGO_DEBUG=true python mySite/manage.py test gameAI.tests imposterGame.tests couplesQuestions.tests
python mySite/manage.py check --deploy
python mySite/manage.py makemigrations --check --dry-run
```

Run the last two commands with real production environment settings. Tests use mocked providers; they do not contact the private Ollama server.

Implementation references: [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [Channels WebSocket security](https://channels.readthedocs.io/en/stable/topics/security.html), [Ollama chat API](https://docs.ollama.com/api/chat), and [Ollama API compatibility](https://docs.ollama.com/api/openai-compatibility).
