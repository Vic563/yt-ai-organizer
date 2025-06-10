"""Middleware for authentication and error handling"""

import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from exceptions import AppException, ErrorResponse

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to handle exceptions and return consistent error responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        try:
            # Add timing
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except AppException as exc:
            # Handle our custom exceptions
            logger.error(f"Application error: {exc.message}", extra={
                "request_id": request_id,
                "status_code": exc.status_code,
                "details": exc.details
            })
            
            error_response = ErrorResponse(
                error=exc.__class__.__name__,
                message=exc.message,
                status_code=exc.status_code,
                details=exc.details,
                request_id=request_id
            )
            
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response.dict()
            )
            
        except HTTPException as exc:
            # Handle FastAPI HTTP exceptions
            logger.error(f"HTTP error: {exc.detail}", extra={
                "request_id": request_id,
                "status_code": exc.status_code
            })
            
            error_response = ErrorResponse(
                error="HTTPException",
                message=str(exc.detail),
                status_code=exc.status_code,
                request_id=request_id
            )
            
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response.dict()
            )
            
        except Exception as exc:
            # Handle unexpected exceptions
            logger.exception(f"Unexpected error: {str(exc)}", extra={
                "request_id": request_id
            })
            
            error_response = ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id
            )
            
            return JSONResponse(
                status_code=500,
                content=error_response.dict()
            )

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Log request
        logger.info(f"Request: {request.method} {request.url.path}", extra={
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "request_id": getattr(request.state, "request_id", None)
        })
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response
        logger.info(f"Response: {response.status_code} in {process_time:.3f}s", extra={
            "status_code": response.status_code,
            "process_time": process_time,
            "request_id": getattr(request.state, "request_id", None)
        })
        
        return response

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to check authentication on protected routes"""
    
    # Public endpoints that don't require authentication
    PUBLIC_PATHS = {
        "/",
        "/api/health",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/docs",
        "/redoc",
        "/openapi.json"
    }
    
    # Paths that start with these prefixes are public
    PUBLIC_PREFIXES = [
        "/assets/",
        "/static/"
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if path is public
        path = request.url.path
        
        # Exact match
        if path in self.PUBLIC_PATHS:
            return await call_next(request)
        
        # Prefix match
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)
        
        # For other paths, authentication is handled by dependencies
        # This middleware just adds security headers
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients = {}  # IP -> [timestamps]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get client IP
        client_ip = request.client.host
        current_time = time.time()
        
        # Initialize or get client timestamps
        if client_ip not in self.clients:
            self.clients[client_ip] = []
        
        # Remove old timestamps
        self.clients[client_ip] = [
            ts for ts in self.clients[client_ip] 
            if current_time - ts < self.period
        ]
        
        # Check rate limit
        if len(self.clients[client_ip]) >= self.calls:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RateLimitExceeded",
                    "message": "Too many requests",
                    "retry_after": self.period
                }
            )
        
        # Add current timestamp
        self.clients[client_ip].append(current_time)
        
        # Process request
        return await call_next(request)