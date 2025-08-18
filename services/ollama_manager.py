import asyncio
import logging
import subprocess
import psutil
import time
import os
import signal
import requests
from config import settings

logger = logging.getLogger(__name__)

class OllamaManager:
    """Manages Ollama service and model availability"""
    
    def __init__(self):
        self.process = None
        self.is_running = False
        # Clean the URL - remove any API endpoints like the working code does
        raw_url = getattr(settings, 'LOCAL_URL', 'http://localhost:11434')
        self.base_url = raw_url.split('/api')[0] if '/api' in raw_url else raw_url
        self.model_name = getattr(settings, 'LOCAL_LLM_MODEL_NAME')
    
    def _normalize_host_url(self, host: str) -> str:
        """Ensure host URL is properly formatted."""
        if not host.startswith(('http://', 'https://')):
            host = f'http://{host}'
        return host.rstrip('/')
    
    async def is_ollama_running(self) -> bool:
        """Check if Ollama service is running using sync requests like the working code"""
        try:
            normalized_host = self._normalize_host_url(self.base_url)
            
            # Try the root endpoint first (like working code)
            response = requests.get(normalized_host, timeout=5)
            if response.status_code == 200:
                return True
            
            # If root fails, try the /api/tags endpoint as backup
            response = requests.get(f"{normalized_host}/api/tags", timeout=5)
            return response.status_code == 200
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Server check failed: {e}")
            return False
    
    def _find_ollama_processes(self):
        """Find existing Ollama processes"""
        ollama_processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'ollama' in proc.info['name'].lower():
                        ollama_processes.append(proc)
                    elif proc.info['cmdline'] and any('ollama' in arg.lower() for arg in proc.info['cmdline']):
                        ollama_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug(f"Error finding Ollama processes: {e}")
        return ollama_processes
    
    def _find_running_ollama_servers(self) -> list:
        """Find any running Ollama servers on common ports."""
        common_ports = [11434, 11435, 11436]  # Default and some alternatives
        running_servers = []
        
        for port in common_ports:
            try:
                test_url = f"http://localhost:{port}"
                response = requests.get(test_url, timeout=2)
                if response.status_code == 200:
                    running_servers.append(test_url)
            except:
                continue
        
        return running_servers
    
    def _check_ollama_installation(self) -> bool:
        """Check if Ollama is properly installed and accessible."""
        try:
            # First check if the command exists
            result = subprocess.run(
                ["ollama", "--version"], 
                capture_output=True, 
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"Found Ollama: {version}")
                return True
            else:
                logger.error(f"Ollama command failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.critical("❌ Ollama command not found. Please install from https://ollama.com/")
            return False
        except subprocess.TimeoutExpired:
            logger.error("❌ Ollama command timed out. Installation might be corrupted.")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking Ollama installation: {e}")
            return False
    
    def _wait_for_server_ready(self, timeout: int = 60) -> bool:
        """Wait for the server to become ready with exponential backoff."""
        start_time = time.time()
        wait_time = 0.5
        max_wait = 3.0
        
        logger.info(f"Waiting for Ollama server to start (timeout: {timeout}s)...")
        
        while time.time() - start_time < timeout:
            # Use sync version from working code
            if asyncio.run(self.is_ollama_running()):
                elapsed = time.time() - start_time
                logger.info(f"Server is ready! (took {elapsed:.1f}s)")
                return True
            
            elapsed = time.time() - start_time
            logger.debug(f"Still waiting... ({elapsed:.1f}s elapsed)")
            time.sleep(wait_time)
            wait_time = min(wait_time * 1.2, max_wait)  # Exponential backoff
        
        return False

    async def start_ollama_service(self):
        """Start Ollama service if not running - following working code pattern"""
        logger.info(f"Starting Ollama manager for model '{self.model_name}' at {self.base_url}")

        # 1. Check if server is already running
        if await self.is_ollama_running():
            logger.info("Ollama server is already running")
            self.is_running = True
            return True
        
        # Check if there are other Ollama servers running
        running_servers = self._find_running_ollama_servers()
        if running_servers:
            logger.warning(f"Found Ollama servers running on: {running_servers}")
            logger.warning(f"But none responding at configured URL: {self.base_url}")
        
        logger.info("Starting Ollama server...")
        
        # Check if ollama is properly installed
        if not self._check_ollama_installation():
            return False
        
        try:
            # Start the server process - using working code approach
            logger.info("Launching Ollama server process...")
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            logger.info(f"Started Ollama process with PID: {self.process.pid}")
            
            # Give the process a moment to start
            time.sleep(2)
            
            # Check if the process is still running
            if self.process.poll() is not None:
                # Process has already terminated
                stdout, stderr = self.process.communicate()
                logger.error(f"Ollama server process terminated immediately:")
                if stderr:
                    logger.error(f"STDERR: {stderr.decode().strip()}")
                if stdout:
                    logger.error(f"STDOUT: {stdout.decode().strip()}")
                return False
            
            # Wait for the server to become ready
            if not self._wait_for_server_ready(timeout=60):
                logger.error("Ollama server failed to start within timeout period")
                
                # Check if process is still running and get any error output
                if self.process.poll() is None:
                    logger.info("Server process is still running but not responding")
                else:
                    stdout, stderr = self.process.communicate()
                    if stderr:
                        logger.error(f"Server error output: {stderr.decode().strip()}")
                    if stdout:
                        logger.info(f"Server output: {stdout.decode().strip()}")
                
                self.stop_ollama_service()
                return False
                
            logger.info(f"Ollama server started successfully at {self.base_url}")
            self.is_running = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Ollama server: {e}")
            return False
    
    async def is_model_available(self, model_name: str) -> bool:
        """Check if specific model is available - using working code approach"""
        if not await self.is_ollama_running():
            return False
            
        try:
            normalized_host = self._normalize_host_url(self.base_url)
            response = requests.get(f"{normalized_host}/api/tags", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            models = data.get("models", [])
            
            # Check for exact match or partial match (handling version tags)
            for model in models:
                model_name_from_api = model.get('name', '')
                if model_name_from_api == model_name or model_name_from_api.startswith(f"{model_name}:"):
                    logger.debug(f"Found model: {model_name_from_api}")
                    return True
                    
            logger.debug(f"Model '{model_name}' not found in available models: {[m.get('name') for m in models]}")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed while checking for model: {e}")
            return False
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse model list response: {e}")
            return False

    async def pull_model(self, model_name: str):
        """Pull model if not available - using working code approach with progress"""
        if await self.is_model_available(model_name):
            logger.info(f"Model {model_name} is already available")
            return True
        
        logger.info(f"Pulling model '{model_name}' from registry...")
        
        try:
            # Start the pull process
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # Monitor the process
            stdout_lines = []
            stderr_lines = []
            
            # Read output in real-time
            while process.poll() is None:
                if process.stdout:
                    line = process.stdout.readline()
                    if line:
                        stdout_lines.append(line.strip())
                        # Show some progress indication
                        if "pulling" in line.lower() or "downloading" in line.lower():
                            logger.info(f"Progress: {line.strip()}")
                
                if process.stderr:
                    line = process.stderr.readline()
                    if line:
                        stderr_lines.append(line.strip())
            
            # Get remaining output
            if process.stdout:
                remaining_stdout = process.stdout.read()
                if remaining_stdout:
                    stdout_lines.extend(remaining_stdout.strip().split('\n'))
            
            if process.stderr:
                remaining_stderr = process.stderr.read()
                if remaining_stderr:
                    stderr_lines.extend(remaining_stderr.strip().split('\n'))
            
            return_code = process.wait()
            
            if return_code == 0:
                logger.info(f"Successfully pulled model '{model_name}'")
                
                # Wait a moment for the model to be fully registered
                time.sleep(2)
                
                # Double-check model availability
                if not await self.is_model_available(model_name):
                    logger.error(f"Model '{model_name}' still not available after pulling")
                    return False
                    
                return True
            else:
                error_msg = '\n'.join(stderr_lines) if stderr_lines else "Unknown error"
                logger.error(f"Failed to pull model '{model_name}'. Error: {error_msg}")
                return False
                
        except FileNotFoundError:
            logger.critical("❌ Ollama command not found. Please install from https://ollama.com/")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while pulling model: {e}")
            return False
    
    def _preload_model(self) -> bool:
        """Pre-load the model into memory with better error handling."""
        logger.info(f"Pre-loading model '{self.model_name}' into memory...")
        
        try:
            normalized_host = self._normalize_host_url(self.base_url)
            
            # First, try to generate a simple response to load the model
            payload = {
                "model": self.model_name,
                "prompt": "Hello",
                "stream": False,
                "options": {
                    "num_predict": 1  # Minimal response to just load the model
                }
            }
            
            response = requests.post(
                f"{normalized_host}/api/generate",
                json=payload,
                timeout=180  # Loading can take time for large models
            )
            
            response.raise_for_status()
            
            # Verify the response
            try:
                response_data = response.json()
                if 'response' in response_data:
                    logger.info(f"✅ Model '{self.model_name}' is loaded and ready")
                    return True
                else:
                    logger.warning(f"Unexpected response format: {response_data}")
                    return False
            except ValueError:  # JSON decode error
                logger.error("Failed to parse model loading response")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while loading model '{self.model_name}'. The model might be too large or the server is overloaded.")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to pre-load model '{self.model_name}': {e}")
            return False

    async def ensure_model_running(self):
        """Ensure Ollama service is running and model is available"""
        try:
            # Start Ollama service
            if not await self.start_ollama_service():
                raise RuntimeError("Failed to start Ollama service")
            
            # Pull model if needed
            if not await self.pull_model(self.model_name):
                raise RuntimeError(f"Failed to pull model {self.model_name}")
            
            # Pre-load the model
            if not self._preload_model():
                logger.warning("Failed to pre-load model, but continuing anyway")
                # Don't return False here as the server might still work
            
            logger.info("Ollama service and model are ready")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure model running: {e}")
            raise
    
    def stop_ollama_service(self):
        """Stop Ollama service - using working code approach"""
        if self.process and self.process.poll() is None:
            logger.info("Stopping the Ollama server started by this script...")
            try:
                # Try graceful termination first
                if os.name == 'nt':  # Windows
                    self.process.terminate()
                else:  # Unix-like
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                
                # Wait for graceful exit
                try:
                    self.process.wait(timeout=10)
                    logger.info("Ollama server stopped gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning("Server did not terminate gracefully. Forcing kill...")
                    if os.name == 'nt':
                        self.process.kill()
                    else:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    self.process.wait()
                    logger.info("Ollama server killed")
                    
            except ProcessLookupError:
                logger.info("Server process already terminated")
            except Exception as e:
                logger.error(f"Error while stopping Ollama: {e}")
            finally:
                self.process = None
                self.is_running = False
        else:
            logger.info("No Ollama server process to stop")
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except:
                pass