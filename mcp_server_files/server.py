"""Core server setup and routing for MCP Server.

Defines the FastAPI application with:
- Tool discovery endpoint (/api/tools)
- Tool execution endpoint (/api/tools/{tool_name}/execute)
- Health check endpoint (/health)
- Dashboard UI for secrets management and monitoring
"""

import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

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
    
    # Add session middleware for auth cookies
    session_secret = settings.auth_session_secret or secrets.token_hex(32)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        session_cookie="jexida_session",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    
    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Set up templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    
    # -------------------------------------------------------------------------
    # Authentication Helpers
    # -------------------------------------------------------------------------
    
    def is_auth_enabled() -> bool:
        """Check if authentication is enabled."""
        # TEMPORARILY DISABLED - return False to allow access
        return False
        # return bool(settings.auth_password)
    
    def is_authenticated(request: Request) -> bool:
        """Check if the current request is authenticated."""
        if not is_auth_enabled():
            return True  # Auth disabled, everyone is authenticated
        if "session" not in request.scope:
            return False
        session = request.scope.get("session", {})
        return session.get("authenticated", False)
    
    def require_auth(request: Request) -> bool:
        """Dependency that requires authentication."""
        if not is_authenticated(request):
            raise HTTPException(status_code=401, detail="Not authenticated")
        return True
    
    # -------------------------------------------------------------------------
    # Login/Logout Routes
    # -------------------------------------------------------------------------
    
    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, error: str = None, next: str = "/"):
        """Show login page."""
        if not is_auth_enabled():
            return RedirectResponse(url="/", status_code=303)
        
        if is_authenticated(request):
            return RedirectResponse(url=next, status_code=303)
        
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": error,
            "next": next,
            "page_title": "Login"
        })
    
    @app.post("/login", response_class=HTMLResponse)
    async def login_submit(
        request: Request,
        password: str = Form(...),
        next: str = Form("/")
    ):
        """Process login form."""
        if not is_auth_enabled():
            return RedirectResponse(url="/", status_code=303)
        
        if password == settings.auth_password:
            # Set session - ensure session is in scope first
            if "session" not in request.scope:
                request.scope["session"] = {}
            request.scope["session"]["authenticated"] = True
            # Also set via request.session for SessionMiddleware
            try:
                if hasattr(request, 'session'):
                    request.session["authenticated"] = True
            except (AttributeError, KeyError):
                # Session not available, but we set it in scope
                pass
            logger.info("User authenticated successfully")
            # Use absolute URL to ensure cookie is set
            response = RedirectResponse(url=next, status_code=303)
            return response
        
        logger.warning("Failed login attempt")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid password",
            "next": next,
            "page_title": "Login"
        })
    
    @app.get("/logout")
    async def logout(request: Request):
        """Log out and clear session."""
        request.session.clear()
        logger.info("User logged out")
        return RedirectResponse(url="/login", status_code=303)
    
    # -------------------------------------------------------------------------
    # Auth Middleware (redirect to login for protected pages)
    # -------------------------------------------------------------------------
    
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """Check authentication for protected routes - TEMPORARILY DISABLED."""
        # TEMPORARILY DISABLED - allowing all access to load keys
        return await call_next(request)
    
    # Include assistant router if available
    if ASSISTANT_AVAILABLE and assistant_router:
        app.include_router(assistant_router)
        logger.info("AI Assistant router included")
    
    # Import database components (lazy import to avoid circular dependencies)
    def get_db_session():
        """Get a database session, properly managing the connection."""
        from database import get_session_local
        SessionLocal = get_session_local()
        db = SessionLocal()
        return db
    
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
            
            # Create reference tables and seed data
            try:
                from assistant.references.models import (
                    ReferenceSnippet, ReferenceProfile, 
                    ReferenceProfileSnippet, ReferenceLog
                )
                Base.metadata.create_all(bind=get_engine())
                logger.info("Reference tables initialized")
                
                # Seed reference data if tables are empty
                db = get_db_session()
                try:
                    snippet_count = db.query(ReferenceSnippet).count()
                    if snippet_count == 0:
                        from assistant.references.seed import seed_references
                        snippets, profiles = seed_references(db)
                        logger.info(f"Seeded {snippets} reference snippets")
                except Exception as seed_err:
                    logger.warning(f"Could not seed reference data: {seed_err}")
                finally:
                    db.close()
                    
            except ImportError as ref_err:
                logger.debug(f"Reference module not available: {ref_err}")
            
            logger.info("Database initialized successfully")
            
            # Reload settings to pick up secrets from database
            # This is needed because get_settings() was called during import
            # before the DB was fully initialized
            reload_settings()
            logger.info("Settings reloaded from database")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
    
    # -------------------------------------------------------------------------
    # Admin API Endpoints for Reference Management
    # -------------------------------------------------------------------------
    
    @app.get("/api/admin/references/snippets")
    async def list_reference_snippets(
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
    ):
        """List all reference snippets with optional filtering.
        
        Args:
            category: Filter by category
            is_active: Filter by active status
            
        Returns:
            List of reference snippet dictionaries
        """
        try:
            from assistant.references.service import list_reference_snippets as list_snippets
            
            db = get_db_session()
            try:
                filters = {}
                if category:
                    filters["category"] = category
                if is_active is not None:
                    filters["is_active"] = is_active
                
                snippets = list_snippets(db, filters if filters else None)
                return {"snippets": [s.to_dict() for s in snippets]}
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
    
    @app.get("/api/admin/references/snippets/{snippet_key}")
    async def get_reference_snippet(snippet_key: str):
        """Get a specific reference snippet by key.
        
        Args:
            snippet_key: Unique key of the snippet
            
        Returns:
            Reference snippet dictionary
        """
        try:
            from assistant.references.service import get_reference_snippet_by_key
            
            db = get_db_session()
            try:
                snippet = get_reference_snippet_by_key(db, snippet_key)
                if snippet is None:
                    raise HTTPException(status_code=404, detail="Snippet not found")
                return snippet.to_dict()
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
    
    @app.post("/api/admin/references/snippets")
    async def create_reference_snippet_endpoint(request: Dict[str, Any]):
        """Create a new reference snippet.
        
        Args:
            request: Snippet data including key, title, content, category, etc.
            
        Returns:
            Created snippet dictionary
        """
        try:
            from assistant.references.service import create_reference_snippet
            from assistant.references.models import ReferenceCategory
            
            db = get_db_session()
            try:
                # Convert category string to enum
                category = request.get("category", "other")
                if isinstance(category, str):
                    category = ReferenceCategory(category)
                
                snippet = create_reference_snippet(
                    db_session=db,
                    key=request["key"],
                    title=request["title"],
                    content=request["content"],
                    category=category,
                    tags=request.get("tags"),
                    applicable_tools=request.get("applicable_tools"),
                    applicable_roles=request.get("applicable_roles"),
                    applicable_modes=request.get("applicable_modes"),
                    applicable_pages=request.get("applicable_pages"),
                    is_active=request.get("is_active", True),
                )
                return snippet.to_dict()
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
    
    @app.put("/api/admin/references/snippets/{snippet_id}")
    async def update_reference_snippet_endpoint(snippet_id: int, request: Dict[str, Any]):
        """Update an existing reference snippet.
        
        Args:
            snippet_id: ID of the snippet to update
            request: Fields to update
            
        Returns:
            Updated snippet dictionary
        """
        try:
            from assistant.references.service import update_reference_snippet
            from assistant.references.models import ReferenceCategory
            
            db = get_db_session()
            try:
                # Convert category string to enum if present
                if "category" in request and isinstance(request["category"], str):
                    request["category"] = ReferenceCategory(request["category"])
                
                snippet = update_reference_snippet(db, snippet_id, **request)
                if snippet is None:
                    raise HTTPException(status_code=404, detail="Snippet not found")
                return snippet.to_dict()
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
    
    @app.get("/api/admin/references/profiles")
    async def list_reference_profiles_endpoint():
        """List all reference profiles.
        
        Returns:
            List of reference profile dictionaries
        """
        try:
            from assistant.references.service import list_reference_profiles
            
            db = get_db_session()
            try:
                profiles = list_reference_profiles(db)
                return {"profiles": [p.to_dict() for p in profiles]}
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
    
    @app.get("/api/admin/references/profiles/{profile_key}")
    async def get_reference_profile(profile_key: str):
        """Get a specific reference profile by key with its snippets.
        
        Args:
            profile_key: Unique key of the profile
            
        Returns:
            Profile dictionary with associated snippets
        """
        try:
            from assistant.references.service import get_reference_profile_by_key
            
            db = get_db_session()
            try:
                profile = get_reference_profile_by_key(db, profile_key)
                if profile is None:
                    raise HTTPException(status_code=404, detail="Profile not found")
                
                result = profile.to_dict()
                # Include snippets in order
                result["snippets"] = [
                    {
                        "order_index": assoc.order_index,
                        **assoc.snippet.to_dict()
                    }
                    for assoc in sorted(profile.snippet_associations, key=lambda a: a.order_index)
                ]
                return result
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
    
    @app.post("/api/admin/references/profiles")
    async def create_reference_profile_endpoint(request: Dict[str, Any]):
        """Create a new reference profile.
        
        Args:
            request: Profile data including key, name, description, is_default
            
        Returns:
            Created profile dictionary
        """
        try:
            from assistant.references.service import create_reference_profile
            
            db = get_db_session()
            try:
                profile = create_reference_profile(
                    db_session=db,
                    key=request["key"],
                    name=request["name"],
                    description=request.get("description"),
                    is_default=request.get("is_default", False),
                )
                return profile.to_dict()
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
    
    @app.post("/api/admin/references/profiles/{profile_id}/snippets")
    async def add_snippet_to_profile_endpoint(
        profile_id: int,
        request: Dict[str, Any],
    ):
        """Add a snippet to a profile.
        
        Args:
            profile_id: ID of the profile
            request: Contains snippet_id and optional order_index
            
        Returns:
            Association details
        """
        try:
            from assistant.references.service import add_snippet_to_profile
            
            db = get_db_session()
            try:
                assoc = add_snippet_to_profile(
                    db_session=db,
                    profile_id=profile_id,
                    snippet_id=request["snippet_id"],
                    order_index=request.get("order_index", 0),
                )
                if assoc is None:
                    raise HTTPException(status_code=404, detail="Profile or snippet not found")
                return {"success": True, "order_index": assoc.order_index}
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
    
    @app.delete("/api/admin/references/profiles/{profile_id}/snippets/{snippet_id}")
    async def remove_snippet_from_profile_endpoint(profile_id: int, snippet_id: int):
        """Remove a snippet from a profile.
        
        Args:
            profile_id: ID of the profile
            snippet_id: ID of the snippet to remove
            
        Returns:
            Success status
        """
        try:
            from assistant.references.service import remove_snippet_from_profile
            
            db = get_db_session()
            try:
                success = remove_snippet_from_profile(db, profile_id, snippet_id)
                if not success:
                    raise HTTPException(status_code=404, detail="Association not found")
                return {"success": True}
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
    
    @app.get("/api/admin/references/logs")
    async def list_reference_logs(
        conversation_id: Optional[int] = None,
        limit: int = 50,
    ):
        """List reference logs, optionally filtered by conversation.
        
        Args:
            conversation_id: Optional conversation ID to filter by
            limit: Maximum number of logs to return
            
        Returns:
            List of reference log dictionaries
        """
        try:
            from assistant.references.models import ReferenceLog
            
            db = get_db_session()
            try:
                query = db.query(ReferenceLog)
                if conversation_id:
                    query = query.filter(ReferenceLog.conversation_id == conversation_id)
                
                logs = query.order_by(ReferenceLog.created_at.desc()).limit(limit).all()
                return {"logs": [log.to_dict() for log in logs]}
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
    
    @app.get("/api/admin/references/logs/{log_id}")
    async def get_reference_log(log_id: int):
        """Get a specific reference log by ID.
        
        Args:
            log_id: ID of the reference log
            
        Returns:
            Reference log dictionary with full details
        """
        try:
            from assistant.references.models import ReferenceLog
            
            db = get_db_session()
            try:
                log = db.query(ReferenceLog).filter(ReferenceLog.id == log_id).first()
                if log is None:
                    raise HTTPException(status_code=404, detail="Reference log not found")
                return log.to_dict()
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
    
    @app.post("/api/admin/references/seed")
    async def seed_references_endpoint(force: bool = False):
        """Manually trigger reference seeding.
        
        Args:
            force: If True, update existing snippets
            
        Returns:
            Seeding results
        """
        try:
            from assistant.references.seed import seed_references
            
            db = get_db_session()
            try:
                snippets_created, profiles_created = seed_references(db, force=force)
                return {
                    "success": True,
                    "snippets_created": snippets_created,
                    "profiles_created": profiles_created,
                }
            finally:
                db.close()
        except ImportError:
            raise HTTPException(status_code=501, detail="Reference module not available")
    
    return app


# Create the app instance
app = create_app()
