"""
Health Check Service for B2500 Meter

Provides HTTP health check endpoints for monitoring service health.
Compatible with both Home Assistant addon watchdog and Docker health checks.
"""

import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from config.logger import logger


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints."""
    
    def do_GET(self):
        """Handle GET requests to health check endpoints."""
        # Normalize path to handle trailing slashes
        normalized_path = self.path.rstrip('/')
        if normalized_path in ['/health', '/api']:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            response = b'{"status": "healthy", "service": "b2500-meter"}'
            self.wfile.write(response)
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = b'{"error": "Not Found"}'
            self.wfile.write(response)
    
    def do_HEAD(self):
        """Handle HEAD requests (some health checkers use HEAD)."""
        # Normalize path to handle trailing slashes
        normalized_path = self.path.rstrip('/')
        if normalized_path in ['/health', '/api']:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default HTTP server logging to avoid spam."""
        pass


class HealthCheckService:
    """Health check service manager."""
    
    def __init__(self, port=52500, bind_address='localhost'):
        self.port = port
        self.bind_address = bind_address
        self.server = None
        self.server_thread = None
        self._running = False
    
    def start(self):
        """Start the health check HTTP server."""
        if self._running:
            logger.warning("Health check service is already running")
            return False
        
        try:
            self.server = HTTPServer((self.bind_address, self.port), HealthCheckHandler)
            self.server_thread = threading.Thread(
                target=self._run_server, 
                name="HealthCheckService",
                daemon=True
            )
            self.server_thread.start()
            
            # Give the server a moment to start and verify it's working
            time.sleep(0.5)
            if not self.server_thread.is_alive():
                logger.error("Health check service thread failed to start")
                return False
                
            self._running = True
            logger.info(f"Health check service started on {self.bind_address}:{self.port}")
            
            # Test the endpoint to ensure it's working
            if self.test_endpoint():
                logger.debug("Health check endpoint test passed")
            else:
                logger.warning("Health check endpoint test failed, but service is running")
                
            return True
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.error(f"Port {self.port} is already in use. Health check service not started.")
            else:
                logger.error(f"Failed to bind to {self.bind_address}:{self.port}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to start health check service: {e}")
            return False
    
    def stop(self):
        """Stop the health check HTTP server."""
        if not self._running:
            return
        
        try:
            if self.server:
                self.server.shutdown()
                self.server.server_close()
            
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5.0)
            
            self._running = False
            logger.info("Health check service stopped")
        except Exception as e:
            logger.error(f"Error stopping health check service: {e}")
    
    def _run_server(self):
        """Run the HTTP server (internal method)."""
        try:
            self.server.serve_forever()
        except Exception as e:
            if self._running:  # Only log if we weren't intentionally shut down
                logger.error(f"Health check server error: {e}")
    
    def is_running(self):
        """Check if the health check service is running."""
        return self._running and self.server_thread and self.server_thread.is_alive()
    
    def test_endpoint(self):
        """Test the health check endpoint (for debugging)."""
        import urllib.request
        import urllib.error
        
        try:
            url = f"http://{self.bind_address}:{self.port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status == 200
        except Exception as e:
            logger.debug(f"Health check test failed: {e}")
            return False


# Global health service instance
_health_service = None


def start_health_service(port=52500, bind_address='localhost'):
    """
    Start the global health check service.
    
    Args:
        port (int): Port to bind to (default: 8124)
        bind_address (str): Address to bind to (default: 'localhost')
    
    Returns:
        bool: True if started successfully, False otherwise
    """
    global _health_service
    
    if _health_service and _health_service.is_running():
        logger.debug("Health service already running")
        return True
    
    _health_service = HealthCheckService(port=port, bind_address=bind_address)
    return _health_service.start()


def stop_health_service():
    """Stop the global health check service."""
    global _health_service
    
    if _health_service:
        _health_service.stop()
        _health_service = None


def is_health_service_running():
    """Check if the global health service is running."""
    global _health_service
    return _health_service and _health_service.is_running()


# Cleanup on module exit
import atexit
atexit.register(stop_health_service) 