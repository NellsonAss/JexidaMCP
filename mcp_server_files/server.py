"""Core server setup and routing for MCP Server.

Defines the FastAPI application with:
- Tool discovery endpoint (/api/tools)
- Tool execution endpoint (/api/tools/{tool_name}/execute)
- Health check endpoint (/health)
- Dashboard UI for secrets management and monitoring
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from config import get_settings, reload_settings
from logging_config import get_logger, setup_logging
from tool_registry import get_registry

# Import assistant router
try:
    from assistant.router import router as assistant_router
    ASSISTANT_AVAILABLE = True
except ImportError:
    ASSISTANT_AVAILABLE = False
    assistant_router = None

# Initialize logging
settings = get_settings()
setup_logging(settings.mcp_log_level)
logger = get_logger(__name__)

# Template and static file paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


# Response models
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


class ToolExecutionRequest(BaseModel):
    """Request body for tool execution."""
    # Parameters are passed as a dict, validated by tool's input schema
    class Config:
        extra = "allow"


class ToolExecutionResponse(BaseModel):
    """Response for tool execution."""
    success: bool
    result: Dict[str, Any] = {}
    error: str = ""


# Create FastAPI app
def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI instance
    """
    app = FastAPI(
        title="JexidaMCP Server",
        description="MCP Server for Azure management and automation",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Set up templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    
    # Include assistant router if available
    if ASSISTANT_AVAILABLE and assistant_router:
        app.include_router(assistant_router)
        logger.info("AI Assistant router included")
    
    # Import database components (lazy import to avoid circular dependencies)
    def get_db_session():
        from database import get_db
        return next(get_db())
    
    # -------------------------------------------------------------------------
    # Health and API Endpoints
    # -------------------------------------------------------------------------
    
    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Health check endpoint."""
        return HealthResponse(status="healthy", version="0.1.0")
    
    @app.get("/api/tools")
    async def list_tools():
        """List all available tools with their schemas.
        
        Returns:
            List of tool definitions with input/output schemas
        """
        registry = get_registry()
        return registry.get_manifest()
    
    @app.post("/api/tools/{tool_name}/execute", response_model=ToolExecutionResponse)
    async def execute_tool(
        tool_name: str,
        request: Dict[str, Any]
    ) -> ToolExecutionResponse:
        """Execute a specific tool.
        
        Args:
            tool_name: Name of the tool to execute
            request: Tool parameters
            
        Returns:
            Tool execution result
            
        Raises:
            HTTPException: If tool not found or execution fails
        """
        registry = get_registry()
        tool = registry.get(tool_name)
        
        if tool is None:
            logger.warning(f"Tool not found: {tool_name}")
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{tool_name}' not found"
            )
        
        try:
            logger.info(f"Executing tool: {tool_name}")
            result = await registry.execute(tool_name, request)
            
            return ToolExecutionResponse(
                success=True,
                result=result
            )
            
        except ValidationError as e:
            logger.warning(f"Validation error for tool {tool_name}: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid parameters: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}", exc_info=True)
            return ToolExecutionResponse(
                success=False,
                error=str(e)
            )
    
    # -------------------------------------------------------------------------
    # Dashboard UI Endpoints
    # -------------------------------------------------------------------------
    
    @app.get("/", response_class=HTMLResponse)
    async def dashboard_home(request: Request):
        """Dashboard home page with overview."""
        from database import get_db, Secret
        from dashboard import get_monitoring_data
        
        db = get_db_session()
        try:
            # Get secret counts by service type
            secret_counts = {}
            for service_type in ["azure", "unifi", "synology", "generic"]:
                count = db.query(Secret).filter(Secret.service_type == service_type).count()
                secret_counts[service_type] = count
            
            total_secrets = sum(secret_counts.values())
            
            # Get monitoring data
            monitoring_data = await get_monitoring_data()
            
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "secret_counts": secret_counts,
                "total_secrets": total_secrets,
                "monitoring_data": monitoring_data,
                "page_title": "Dashboard"
            })
        except Exception as e:
            logger.error(f"Dashboard error: {e}", exc_info=True)
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "secret_counts": {"azure": 0, "unifi": 0, "synology": 0, "generic": 0},
                "total_secrets": 0,
                "monitoring_data": {},
                "error": str(e),
                "page_title": "Dashboard"
            })
        finally:
            db.close()
    
    @app.get("/secrets", response_class=HTMLResponse)
    async def secrets_list(request: Request, service_type: Optional[str] = None):
        """List all secrets."""
        from database import get_db, Secret
        
        db = get_db_session()
        try:
            query = db.query(Secret)
            if service_type:
                query = query.filter(Secret.service_type == service_type)
            secrets = query.order_by(Secret.service_type, Secret.name).all()
            
            return templates.TemplateResponse("secrets_list.html", {
                "request": request,
                "secrets": secrets,
                "service_type_filter": service_type,
                "page_title": "Secrets"
            })
        finally:
            db.close()
    
    @app.get("/secrets/new", response_class=HTMLResponse)
    async def secret_new_form(request: Request, service_type: str = "generic"):
        """Show form to create a new secret."""
        # Pre-defined key templates for each service type
        key_templates = {
            "azure": ["tenant_id", "client_id", "client_secret", "subscription_id"],
            "unifi": ["controller_url", "username", "password", "site"],
            "synology": ["url", "username", "password"],
            "generic": []
        }
        
        return templates.TemplateResponse("secret_form.html", {
            "request": request,
            "secret": None,
            "service_type": service_type,
            "key_templates": key_templates.get(service_type, []),
            "page_title": "New Secret"
        })
    
    @app.post("/secrets", response_class=HTMLResponse)
    async def secret_create(
        request: Request,
        name: str = Form(...),
        service_type: str = Form(...),
        key: str = Form(...),
        value: str = Form(...)
    ):
        """Create a new secret."""
        from database import get_db, Secret, encrypt_value
        
        db = get_db_session()
        try:
            # Check for duplicate key within service type
            existing = db.query(Secret).filter(
                Secret.service_type == service_type,
                Secret.key == key
            ).first()
            
            if existing:
                return templates.TemplateResponse("secret_form.html", {
                    "request": request,
                    "secret": None,
                    "service_type": service_type,
                    "key_templates": [],
                    "error": f"A secret with key '{key}' already exists for {service_type}",
                    "page_title": "New Secret"
                })
            
            # Create new secret
            encrypted = encrypt_value(value)
            secret = Secret(
                name=name,
                service_type=service_type,
                key=key,
                encrypted_value=encrypted
            )
            db.add(secret)
            db.commit()
            
            # Reload settings to pick up new secrets
            reload_settings()
            
            logger.info(f"Created secret: {name} ({service_type}/{key})")
            return RedirectResponse(url="/secrets", status_code=303)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create secret: {e}", exc_info=True)
            return templates.TemplateResponse("secret_form.html", {
                "request": request,
                "secret": None,
                "service_type": service_type,
                "key_templates": [],
                "error": str(e),
                "page_title": "New Secret"
            })
        finally:
            db.close()
    
    @app.get("/secrets/{secret_id}/edit", response_class=HTMLResponse)
    async def secret_edit_form(request: Request, secret_id: int):
        """Show form to edit a secret."""
        from database import get_db, Secret
        
        db = get_db_session()
        try:
            secret = db.query(Secret).filter(Secret.id == secret_id).first()
            if not secret:
                raise HTTPException(status_code=404, detail="Secret not found")
            
            return templates.TemplateResponse("secret_form.html", {
                "request": request,
                "secret": secret,
                "service_type": secret.service_type,
                "key_templates": [],
                "page_title": f"Edit Secret: {secret.name}"
            })
        finally:
            db.close()
    
    @app.post("/secrets/{secret_id}", response_class=HTMLResponse)
    async def secret_update(
        request: Request,
        secret_id: int,
        name: str = Form(...),
        value: str = Form(None)
    ):
        """Update an existing secret."""
        from database import get_db, Secret, encrypt_value
        
        db = get_db_session()
        try:
            secret = db.query(Secret).filter(Secret.id == secret_id).first()
            if not secret:
                raise HTTPException(status_code=404, detail="Secret not found")
            
            secret.name = name
            if value:  # Only update value if provided
                secret.encrypted_value = encrypt_value(value)
            
            db.commit()
            
            # Reload settings to pick up updated secrets
            reload_settings()
            
            logger.info(f"Updated secret: {secret.name} (id={secret_id})")
            return RedirectResponse(url="/secrets", status_code=303)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update secret: {e}", exc_info=True)
            return templates.TemplateResponse("secret_form.html", {
                "request": request,
                "secret": secret if 'secret' in locals() else None,
                "service_type": "",
                "key_templates": [],
                "error": str(e),
                "page_title": "Edit Secret"
            })
        finally:
            db.close()
    
    @app.post("/secrets/{secret_id}/delete", response_class=HTMLResponse)
    async def secret_delete(request: Request, secret_id: int):
        """Delete a secret."""
        from database import get_db, Secret
        
        db = get_db_session()
        try:
            secret = db.query(Secret).filter(Secret.id == secret_id).first()
            if not secret:
                raise HTTPException(status_code=404, detail="Secret not found")
            
            name = secret.name
            db.delete(secret)
            db.commit()
            
            # Reload settings to pick up deleted secrets
            reload_settings()
            
            logger.info(f"Deleted secret: {name} (id={secret_id})")
            return RedirectResponse(url="/secrets", status_code=303)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete secret: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    @app.get("/monitoring", response_class=HTMLResponse)
    async def monitoring_dashboard(request: Request):
        """Monitoring dashboard with live data."""
        from dashboard import get_monitoring_data
        
        try:
            monitoring_data = await get_monitoring_data()
            
            return templates.TemplateResponse("monitoring.html", {
                "request": request,
                "monitoring_data": monitoring_data,
                "page_title": "Monitoring"
            })
        except Exception as e:
            logger.error(f"Monitoring error: {e}", exc_info=True)
            return templates.TemplateResponse("monitoring.html", {
                "request": request,
                "monitoring_data": {},
                "error": str(e),
                "page_title": "Monitoring"
            })
    
    @app.get("/assistant", response_class=HTMLResponse)
    async def assistant_page(request: Request):
        """AI Assistant chat interface."""
        return templates.TemplateResponse("assistant.html", {
            "request": request,
            "page_title": "AI Assistant"
        })
    
    @app.post("/actions/trigger", response_class=HTMLResponse)
    async def trigger_action(
        request: Request,
        tool_name: str = Form(...),
        parameters: str = Form("{}")
    ):
        """Trigger an MCP tool action from the dashboard."""
        import json
        
        registry = get_registry()
        tool = registry.get(tool_name)
        
        if tool is None:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        try:
            params = json.loads(parameters)
            result = await registry.execute(tool_name, params)
            
            return templates.TemplateResponse("action_result.html", {
                "request": request,
                "tool_name": tool_name,
                "success": True,
                "result": result,
                "page_title": f"Action: {tool_name}"
            })
        except json.JSONDecodeError as e:
            return templates.TemplateResponse("action_result.html", {
                "request": request,
                "tool_name": tool_name,
                "success": False,
                "error": f"Invalid JSON parameters: {e}",
                "page_title": f"Action: {tool_name}"
            })
        except Exception as e:
            logger.error(f"Action trigger failed: {tool_name}", exc_info=True)
            return templates.TemplateResponse("action_result.html", {
                "request": request,
                "tool_name": tool_name,
                "success": False,
                "error": str(e),
                "page_title": f"Action: {tool_name}"
            })
    
    # -------------------------------------------------------------------------
    # HTMX Partial Endpoints
    # -------------------------------------------------------------------------
    
    @app.get("/partials/secrets-table", response_class=HTMLResponse)
    async def secrets_table_partial(request: Request, service_type: Optional[str] = None):
        """HTMX partial: secrets table."""
        from database import get_db, Secret
        
        db = get_db_session()
        try:
            query = db.query(Secret)
            if service_type:
                query = query.filter(Secret.service_type == service_type)
            secrets = query.order_by(Secret.service_type, Secret.name).all()
            
            return templates.TemplateResponse("partials/secrets_table.html", {
                "request": request,
                "secrets": secrets
            })
        finally:
            db.close()
    
    @app.get("/partials/monitoring-cards", response_class=HTMLResponse)
    async def monitoring_cards_partial(request: Request):
        """HTMX partial: monitoring cards for auto-refresh."""
        from dashboard import get_monitoring_data
        
        try:
            monitoring_data = await get_monitoring_data()
            
            return templates.TemplateResponse("partials/monitoring_cards.html", {
                "request": request,
                "monitoring_data": monitoring_data
            })
        except Exception as e:
            return templates.TemplateResponse("partials/monitoring_cards.html", {
                "request": request,
                "monitoring_data": {},
                "error": str(e)
            })
    
    # -------------------------------------------------------------------------
    # Database initialization on startup
    # -------------------------------------------------------------------------
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize database on startup."""
        try:
            from database import init_db, Base, get_engine
            init_db()
            
            # Also create assistant tables
            try:
                from assistant.models import Conversation, Message, ActionLog
                Base.metadata.create_all(bind=get_engine())
                logger.info("Assistant tables initialized")
            except ImportError:
                logger.debug("Assistant module not available, skipping assistant table creation")
            
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
    
    return app


# Create the app instance
app = create_app()
