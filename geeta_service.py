#Start a service to keep the website running!
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os
import sys
import time
import threading

class GeetaDocumentQAService(win32serviceutil.ServiceFramework):
    _svc_name_ = "GeetaDocumentQA"
    _svc_display_name_ = "Geeta Document QA System"
    _svc_description_ = "Document Question Answering System for Bhagavad Geeta with Gemini AI"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.process = None
        self.is_running = True
        
    def SvcStop(self):
        """Called when Windows wants to stop the service"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except:
                pass
        win32event.SetEvent(self.hWaitStop)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        
    def SvcDoRun(self):
        """Main service entry point"""
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                             servicemanager.PYS_SERVICE_STARTED,
                             (self._svc_name_, ''))
        self.main()
        
    def main(self):
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            os.chdir(script_dir)
            
            # Log startup information
            servicemanager.LogInfoMsg(f"Starting Geeta Document QA Service from: {script_dir}")
            servicemanager.LogInfoMsg(f"Python executable: {sys.executable}")
            servicemanager.LogInfoMsg(f"Current directory: {os.getcwd()}")
            
            # Set environment variables for service context
            os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            
            # Create a proper temp directory for the service
            service_temp_dir = os.path.join(os.environ['SystemDrive'], 'Temp', 'GeetaService')
            os.makedirs(service_temp_dir, exist_ok=True)
            os.environ['TEMP'] = service_temp_dir
            os.environ['TMP'] = service_temp_dir
            
            servicemanager.LogInfoMsg(f"Temp directory set to: {service_temp_dir}")
            
            # Check if webgeeta.py exists
            if not os.path.exists("webgeeta.py"):
                servicemanager.LogErrorMsg("ERROR: webgeeta.py not found!")
                return
            
            servicemanager.LogInfoMsg("Starting Streamlit application...")
            
            # Start Streamlit app with explicit paths
            self.process = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", 
                "webgeeta.py",
                "--server.port=8501",
                "--server.address=0.0.0.0",
                "--server.headless=true",
                "--browser.gatherUsageStats=false",
                "--logger.level=error"
            ], 
            cwd=script_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8')
            
            servicemanager.LogInfoMsg("Streamlit process started successfully")
            servicemanager.LogInfoMsg("Geeta Document QA System should be available at http://localhost:8501")
            
            # Monitor the process
            self.monitor_process()
            
        except Exception as e:
            error_msg = f"Service startup failed: {str(e)}"
            servicemanager.LogErrorMsg(error_msg)
            # Also try to log to a file for debugging
            try:
                with open(os.path.join(script_dir, "service_error.log"), "w") as f:
                    f.write(error_msg)
            except:
                pass
    
    def monitor_process(self):
        """Monitor the Streamlit process and handle output"""
        def read_output():
            while self.is_running and self.process and self.process.poll() is None:
                try:
                    # Read stdout
                    stdout_line = self.process.stdout.readline()
                    if stdout_line:
                        servicemanager.LogInfoMsg(f"STDOUT: {stdout_line.strip()}")
                    
                    # Read stderr
                    stderr_line = self.process.stderr.readline()
                    if stderr_line:
                        servicemanager.LogWarningMsg(f"STDERR: {stderr_line.strip()}")
                        
                except Exception as e:
                    servicemanager.LogErrorMsg(f"Output reading error: {str(e)}")
                    time.sleep(1)
        
        # Start output monitoring in a separate thread
        output_thread = threading.Thread(target=read_output, daemon=True)
        output_thread.start()
        
        # Main service loop
        while self.is_running:
            # Check if process is still running
            if self.process.poll() is not None:
                servicemanager.LogErrorMsg("Streamlit process stopped unexpectedly!")
                break
            
            # Wait for stop signal or timeout
            result = win32event.WaitForSingleObject(self.hWaitStop, 5000)
            if result == win32event.WAIT_OBJECT_0:
                servicemanager.LogInfoMsg("Stop signal received")
                break

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Run as service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(GeetaDocumentQAService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Handle command line
        win32serviceutil.HandleCommandLine(GeetaDocumentQAService)
