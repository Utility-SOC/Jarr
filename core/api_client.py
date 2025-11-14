"""
Reusable HTTP client with retry logic, timeout handling, and session management.
Refactored from ApiWorker in arr_omnitool.py (line 121)
"""

import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class ApiClient:
    """
    Reusable HTTP client with retry logic, timeout handling,
    and session management for all API calls.
    """
    def __init__(self, timeout: int = 30):
        self.session = self._create_session()
        self.session.headers.update({"Accept": "application/json"})
        self.timeout = timeout

    def _create_session(self) -> requests.Session:
        """
        Creates a requests session with retry logic.
        Migrated from arr_omnitool.py (line 137)
        """
        session = requests.Session()
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 503, 504),
        )
        adapter = HTTPAdapter(max_retries=retry)  # Fixed: was max_ri_retries
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def api_request(self, 
                     url: str, 
                     api_key: Optional[str] = None, 
                     service_name: str = "",
                     params: Optional[Dict[str, Any]] = None,
                     method: str = "GET",
                     json_payload: Optional[Dict[str, Any]] = None,
                     timeout: Optional[int] = None) -> Any:
        """
        Generalized API request helper.
        Migrated from arr_omnitool.py (line 200)
        
        Args:
            url: Full URL to request
            api_key: API key for authentication
            service_name: Service type ('jellyfin' uses different auth header)
            params: Query parameters
            method: HTTP method (GET, POST, PUT, DELETE)
            json_payload: JSON body for POST/PUT requests
            timeout: Custom timeout (overrides default)
            
        Returns:
            JSON response as dict/list, or success message
            
        Raises:
            requests.exceptions.HTTPError: On HTTP errors
            requests.exceptions.RequestException: On network errors
        """
        headers = {}
        if api_key:
            if service_name.lower() == "jellyfin":
                headers["X-Emby-Token"] = api_key
            else:
                headers["X-Api-Key"] = api_key
        
        request_timeout = timeout if timeout is not None else self.timeout
        
        try:
            if method.upper() == "GET":
                logger.debug(f"GET {url} params={params}")
                response = self.session.get(url, headers=headers, params=params, timeout=request_timeout)
            elif method.upper() == "POST":
                logger.debug(f"POST {url} json={json_payload}")
                headers["Content-Type"] = "application/json"
                response = self.session.post(url, headers=headers, params=params, json=json_payload, timeout=request_timeout)
            elif method.upper() == "PUT":
                logger.debug(f"PUT {url} json={json_payload}")
                headers["Content-Type"] = "application/json"
                response = self.session.put(url, headers=headers, params=params, json=json_payload, timeout=request_timeout)
            elif method.upper() == "DELETE":
                logger.debug(f"DELETE {url}")
                response = self.session.delete(url, headers=headers, params=params, timeout=request_timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            
            # Handle different success codes
            if response.status_code in [201, 204]:
                return {"status": "success", "message": f"Status Code {response.status_code}"}
            if not response.content:
                return {"status": "success"}

            return response.json()
            
        except requests.exceptions.HTTPError as err:
            logger.error(f"API Request Failed for {method} {url}: {err}")
            if err.response is not None:
                logger.error(f"Response body: {err.response.text[:500]}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error on {method} {url}: {e}")
            raise

    def close(self):
        """Close the session and cleanup resources."""
        if self.session:
            self.session.close()


class ApiWorker(QObject):
    """
    Generic QObject worker for running any function in a separate thread.
    This replaces the monolithic ApiWorker from the original code.
    Plugins will provide their own task functions to this worker.
    """
    finished = pyqtSignal(object, str)  # Emits (result, error_message)
    progress = pyqtSignal(str)          # Emits progress updates
 
    def __init__(self, task_callable: Callable, *args, **kwargs):
        """
        Initialize worker with a callable task.
        
        Args:
            task_callable: Function to execute in thread
            *args: Positional arguments for task_callable
            **kwargs: Keyword arguments for task_callable
        """
        super().__init__()
        self.task_callable = task_callable
        self.args = args
        self.kwargs = kwargs
        self.is_running = True

    def stop(self):
        """Request the worker to stop."""
        self.is_running = False
 
    def run(self):
        """
        Main worker task execution.
        Emits finished signal with (result, error) when complete.
        """
        task_name = getattr(self.task_callable, '__name__', 'unknown')
        self.progress.emit(f"Starting task: {task_name}...")
        
        try:
            result = self.task_callable(*self.args, **self.kwargs)
            if self.is_running:
                self.finished.emit(result, "")
        except Exception as e:
            logger.error(f"Error in worker task '{task_name}': {e}", exc_info=True)
            if self.is_running:
                self.finished.emit(None, str(e))
        finally:
            self.progress.emit(f"Task finished: {task_name}")
