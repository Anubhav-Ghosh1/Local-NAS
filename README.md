# Home NAS

A self-hosted file server for your home network. Browse, upload, edit, and stream
files from one or more root directories, with per-user access control and an
activity log. Built with FastAPI and a static HTML/JS frontend.

## Features

- JWT-based authentication with three roles: `user`, `admin`, `superadmin`
- Multiple storage roots, each with its own access list (`allowed_roots`)
- Browse directories, download and upload files, create folders, rename and delete
- In-browser text editing for common source/config/text file types (1 MB cap)
- Range-request media streaming (video/audio/image) for `<video>`/`<audio>` tags
- Path traversal protection — all file operations are resolved and confined to
  their configured root
- Per-user activity log (`activity.log`), viewable by admins
- User management API (create/delete users, set role, set root access)
- Optional external access via Cloudflare Tunnel (no port forwarding needed)

## Requirements

- Python 3.10+
- pip

## Project structure

```
nas-server/
├── main.py            FastAPI app, router wiring, static file mount
├── config.py           Settings loaded from .env
├── auth.py             Login, JWT issuance, user CRUD, roles
├── roots.py             Root directory registry + path resolution/traversal guard
├── roots_router.py       API for listing/creating/deleting roots (superadmin)
├── files_router.py       Browse, upload, mkdir, rename, delete, text read/write
├── stream_router.py      Range-request media streaming endpoint
├── logs_router.py        Activity log API (admin only)
├── logger.py             Activity log writer
├── static/index.html     Frontend UI
├── users.json          User store (created on first run)
├── roots.json          Root directory registry (created on first run)
├── activity.log         Activity log (created on first run)
├── start.sh              Startup script
├── requirements.txt
├── .env.example
└── .env                 Your local config (not committed)
```

## Setup

1. Clone/copy this project, then move into it:

   ```bash
   cd nas-server
   ```

2. Create a virtual environment (recommended) and install dependencies:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy the example environment file and edit it:

   ```bash
   cp .env.example .env
   ```

   Generate a real `SECRET_KEY`:

   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

   Paste the output into `SECRET_KEY` in `.env`. Also set `FILES_ROOT` to
   wherever you want your default file storage to live.

4. Run the server:

   ```bash
   ./start.sh
   ```

   `start.sh` will auto-create `.env` from `.env.example` if missing, install
   missing dependencies, and start the server with `uvicorn` (auto-reload
   enabled). Alternatively, run directly:

   ```bash
   python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload
   ```

5. Open `http://localhost:8080` in your browser.

## Default login

On first run a default user is created:

- **Username:** `admin`
- **Password:** `admin123`

**Change this password immediately after first login** via the "change
password" API/UI, especially before exposing the server outside your local
network.

## Environment variables

See [`.env.example`](.env.example) for the full list with descriptions.

| Variable                       | Description                                              | Default                     |
| ------------------------------- | ---------------------------------------------------------- | ------------------------------ |
| `SECRET_KEY`                     | Secret used to sign JWTs. Must be long and random in prod. | `CHANGE-THIS-...` (placeholder) |
| `FILES_ROOT`                     | Default root directory for files, created on first run.   | `~/storage/files`             |
| `HOST`                          | Address the server listens on.                             | `0.0.0.0`                    |
| `PORT`                          | Port the server listens on.                                | `8080`                       |
| `ACCESS_TOKEN_EXPIRE_MINUTES`    | JWT expiry in minutes.                                     | `1440` (24 hours)            |

## API overview

All endpoints except `/api/auth/login` require an `Authorization: Bearer <token>`
header (the streaming endpoint also accepts `?token=` as a query param, for
`<video src>` tags that can't set headers).

### Auth (`/api/auth`)

| Method | Path                       | Access      | Description                  |
| ------ | --------------------------- | ----------- | ------------------------------ |
| POST   | `/login`                     | public      | Log in, get a JWT              |
| GET    | `/me`                        | any user    | Current user info              |
| POST   | `/change-password`           | any user    | Change own password            |
| GET    | `/users`                     | admin+      | List users                     |
| POST   | `/users`                     | admin+      | Create user                    |
| PATCH  | `/users/{username}/access`   | superadmin  | Set a user's allowed roots     |
| PATCH  | `/users/{username}/role`     | superadmin  | Set a user's role              |
| DELETE | `/users/{username}`          | admin+      | Delete a user                  |

### Roots (`/api/roots`)

| Method | Path         | Access      | Description                  |
| ------ | ------------- | ----------- | ------------------------------ |
| GET    | `/`            | any user    | List roots visible to caller   |
| POST   | `/`            | superadmin  | Create a new root               |
| DELETE | `/{root_id}`  | superadmin  | Delete a root                  |

### Files (`/api/files`)

| Method | Path                          | Description                          |
| ------ | ------------------------------ | --------------------------------------- |
| GET    | `/{root_id}/{path}`            | Browse a directory or download a file  |
| POST   | `/{root_id}/upload`            | Upload one or more files                |
| POST   | `/{root_id}/mkdir`              | Create a directory                     |
| PATCH  | `/{root_id}/rename`             | Rename a file or directory              |
| GET    | `/{root_id}/text`               | Read a text file's contents (max 1 MB)  |
| PUT    | `/{root_id}/text`                | Write a text file's contents            |
| DELETE | `/{root_id}/{path}`             | Delete a file or directory              |

### Stream (`/api/stream`)

| Method | Path                | Description                                 |
| ------ | -------------------- | ---------------------------------------------- |
| GET    | `/{root_id}/{path}`   | Stream a media file, with HTTP range support   |

### Logs (`/api/logs`)

| Method | Path | Access | Description               |
| ------ | ---- | ------ | ---------------------------- |
| GET    | `/`   | admin+ | Query the activity log        |

## Roles and access control

- **user** — can access only the roots listed in their `allowed_roots`
  (or all roots if `allowed_roots` contains `"*"`).
- **admin** — full access to all roots, can manage users (except granting
  admin/superadmin roles) and view logs.
- **superadmin** — everything admin can do, plus create/delete roots, grant
  roles, and set any user's root access.

## Security notes

- Set a strong, unique `SECRET_KEY` before exposing the server beyond
  localhost.
- Change the default `admin` password immediately.
- File paths are resolved and checked against their root's base path to
  block directory traversal (`../`) attacks.
- The frontend is served over plain HTTP by default; put a reverse proxy or
  tunnel with TLS in front of it for any access beyond your LAN.

## External access

To reach the server from outside your home network without port forwarding,
use a Cloudflare Tunnel:

```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared tunnel --url http://localhost:8080
```

This gives you a temporary `*.trycloudflare.com` URL. For a permanent domain,
see the [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).

## Data files

These files are created automatically on first run and should not be
committed to version control:

- `users.json` — user accounts and password hashes
- `roots.json` — configured storage roots
- `activity.log` — activity log
- `.env` — your local secrets/config
