"""Custom exception classes for the application"""

from typing import Optional, Dict, Any

class AppException(Exception):
    """Base exception for application errors"""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class AuthenticationError(AppException):
    """Authentication related errors"""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=401, details=details)

class AuthorizationError(AppException):
    """Authorization related errors"""
    def __init__(self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=403, details=details)

class ValidationError(AppException):
    """Input validation errors"""
    def __init__(self, message: str = "Invalid input", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)

class NotFoundError(AppException):
    """Resource not found errors"""
    def __init__(self, resource: str, identifier: Any):
        message = f"{resource} with id {identifier} not found"
        super().__init__(message, status_code=404, details={"resource": resource, "id": identifier})

class DatabaseError(AppException):
    """Database operation errors"""
    def __init__(self, message: str = "Database error occurred", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)

class ExternalServiceError(AppException):
    """External service errors (YouTube, Gemini, etc.)"""
    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        full_message = f"{service} error: {message}"
        super().__init__(full_message, status_code=502, details=details)

class RateLimitError(AppException):
    """Rate limiting errors"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, status_code=429, details=details)

class ConfigurationError(AppException):
    """Configuration errors"""
    def __init__(self, message: str = "Configuration error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)

class TranscriptError(AppException):
    """Transcript fetching errors"""
    def __init__(self, video_id: str, message: str = "Failed to fetch transcript"):
        details = {"video_id": video_id}
        super().__init__(message, status_code=500, details=details)

class CostTrackingError(AppException):
    """Cost tracking errors"""
    def __init__(self, message: str = "Cost tracking error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)

# Error response model
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    """Standard error response format"""
    error: str
    message: str
    status_code: int
    details: Dict[str, Any] = {}
    request_id: Optional[str] = None