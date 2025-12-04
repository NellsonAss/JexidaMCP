# JexidaMCP Dashboard

The JexidaMCP Dashboard provides a web-based interface for managing secrets and monitoring your infrastructure.

## Features

- **Secret Management**: Add, edit, and delete credentials for Azure, UniFi, and other services
- **Monitoring Dashboard**: View system health, Azure costs, and UniFi device status
- **Action Triggers**: Execute MCP tools directly from the web interface
- **Encrypted Storage**: All secrets are encrypted at rest using Fernet symmetric encryption

## Getting Started

### 1. Generate Encryption Key

For production use, you must generate a secret encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add this key to your `.env` file:

```
SECRET_ENCRYPTION_KEY=your-generated-key-here
```

### 2. Start the Server

```bash
cd mcp_server_files
./run.sh
```

Or manually:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### 3. Access the Dashboard

Open your browser to: `http://localhost:8080/`

## Dashboard Pages

### Home Dashboard (`/`)

The home dashboard shows:
- Total secret counts by service type
- Quick actions for adding credentials
- System health status
- Available MCP tools overview

### Secrets Management (`/secrets`)

Manage all stored secrets:
- View all secrets (values are never displayed)
- Filter by service type (Azure, UniFi, Generic)
- Add new secrets
- Edit existing secrets
- Delete secrets

### Monitoring (`/monitoring`)

Live monitoring data:
- System health indicators
- Azure cost summaries (when configured)
- UniFi device status (when configured)
- Tool execution interface

## Adding Secrets

### Azure Credentials

1. Go to `/secrets/new?service_type=azure`
2. Add the following secrets:
   - `tenant_id` - Azure AD tenant ID
   - `client_id` - Application (client) ID
   - `client_secret` - Client secret value
   - `subscription_id` - Default subscription ID

### UniFi Credentials

1. Go to `/secrets/new?service_type=unifi`
2. Add the following secrets:
   - `controller_url` - Controller URL (e.g., `https://192.168.1.1`)
   - `username` - Admin username
   - `password` - Admin password
   - `site` - Site ID (default: "default")

### Generic Secrets

Use generic secrets for any custom key-value pairs:

1. Go to `/secrets/new?service_type=generic`
2. Enter a custom key and value

## Security Considerations

### Encryption

- All secret values are encrypted using Fernet (AES-128-CBC)
- The encryption key is stored in the `SECRET_ENCRYPTION_KEY` environment variable
- Secret values are never logged or displayed in the UI

### Access Control

For production deployments, consider:

1. **Reverse Proxy with Auth**: Use nginx with basic auth or OAuth
2. **Network Isolation**: Restrict access to trusted networks
3. **HTTPS**: Always use HTTPS in production

Example nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name mcp.example.com;

    ssl_certificate /etc/ssl/certs/mcp.crt;
    ssl_certificate_key /etc/ssl/private/mcp.key;

    auth_basic "JexidaMCP";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## API Endpoints

The dashboard adds these endpoints to the existing MCP server:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard home |
| `/secrets` | GET | List all secrets |
| `/secrets/new` | GET | Create secret form |
| `/secrets` | POST | Create new secret |
| `/secrets/{id}/edit` | GET | Edit secret form |
| `/secrets/{id}` | POST | Update secret |
| `/secrets/{id}/delete` | POST | Delete secret |
| `/monitoring` | GET | Monitoring dashboard |
| `/actions/trigger` | POST | Execute MCP tool |

## Configuration Priority

Secrets can be configured in multiple places. Priority order (highest first):

1. **Database secrets** (via dashboard)
2. **Environment variables** (via `.env` file)
3. **Default values** (in `config.py`)

This allows you to:
- Use the dashboard for production credentials
- Use `.env` for development/testing
- Fall back to defaults for non-sensitive settings

## Troubleshooting

### "SECRET_ENCRYPTION_KEY not set" warning

This appears in development mode. For production:
1. Generate a key (see above)
2. Set `SECRET_ENCRYPTION_KEY` in your `.env`
3. Set `ENVIRONMENT=production`

### Database not initialized

The database is automatically created on first startup. If you see errors:

```bash
cd mcp_server_files
python -c "from database import init_db; init_db()"
```

### Secrets not loading

Check that:
1. The encryption key matches the one used to create secrets
2. The database file exists (`secrets.db`)
3. The server has read/write access to the database

