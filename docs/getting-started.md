# Getting Started

## Prerequisites

- **Python 3.14+**
- **PostgreSQL** — GAM uses PostgreSQL as its database backend
- **[uv](https://docs.astral.sh/uv/)** — for dependency management
- **AWS CodeArtifact access** — the `griddy` SDK is hosted on a private CodeArtifact registry

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/Thistle-Grow-Software/all-things-griddy.git
cd all-things-griddy/griddy-archive-manager
uv sync
```

## Configuration

GAM reads its database connection and authentication credentials from environment variables.

### Required Variables

| Variable | Description |
|---|---|
| `PG_HOST` | PostgreSQL host (e.g., `localhost`) |
| `PG_PORT` | PostgreSQL port (e.g., `5432`) |
| `PG_DB_NAME` | PostgreSQL database name (e.g., `griddy`) |
| `PG_USER` | PostgreSQL user |
| `PG_PASSWORD` | PostgreSQL password |

### Optional Variables

| Variable | Description |
|---|---|
| `GRIDDY_NFL_EMAIL` | NFL.com email for authenticated API access |
| `GRIDDY_NFL_PASSWORD` | NFL.com password for authenticated API access |
| `MEDIA_ROOT` | Directory for uploaded media files (team logos, etc.) |
| `AWS_CODEARTIFACT_TOKEN` | Authentication token for AWS CodeArtifact |

## Database Setup

Create the PostgreSQL database and apply migrations:

```bash
createdb griddy
uv run manage.py migrate
```

## Create a Superuser

The admin interface requires authentication:

```bash
uv run manage.py createsuperuser
```

## Run the Development Server

```bash
uv run manage.py runserver
```

The Django admin interface is available at [http://localhost:8000/admin/](http://localhost:8000/admin/).

## Shell Aliases

If you work in this project frequently, the following bash aliases (defined in the project's
`.bashrc` conventions) can speed up common operations:

| Alias | Description |
|---|---|
| `gam` | Navigate to the project directory, set env vars, and initialize CodeArtifact auth |
| `uvrm` | Shortcut for `uv run manage.py` (e.g., `uvrm migrate`) |
| `tgf-format` | Run `ruff check --fix` and `ruff format` on the current directory |
| `artifact-token` | Initialize AWS CodeArtifact authentication |

## Next Steps

- Learn about the [Architecture](architecture.md) and data model
- Explore the [Management Commands](commands.md) for data ingestion
- Browse the [API Reference](reference/index.md) for model documentation
