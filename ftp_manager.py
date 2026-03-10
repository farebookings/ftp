import os
import threading
from ftplib import FTP

class FTPWorker:
    def __init__(self, callback_handler):
        self.ftp = None
        self.is_connected = False
        self.callback_handler = callback_handler # Function to send messages to UI thread
        self.stop_event = threading.Event()
        self.lock = threading.Lock() # Lock for thread safety
        
        # Credentials for auto-reconnect
        self.host = None
        self.user = None
        self.password = None

    def _emit(self, event_type, data=None):
        if self.callback_handler:
            self.callback_handler(event_type, data)

    def connect_to_server(self, host, user, password):
        self.host = host
        self.user = user
        self.password = password
        threading.Thread(target=self._connect_thread, daemon=True).start()

    def _connect_thread(self):
        with self.lock:
            try:
                self._perform_connect()
                self._emit("connected", f"Connected to {self.host}")
                self._list_files_internal()
            except Exception as e:
                self.is_connected = False
                self._emit("connection_error", str(e))

    def _perform_connect(self):
        if self.ftp:
            try:
                self.ftp.quit()
            except:
                pass
        self.ftp = FTP(self.host)
        self.ftp.login(user=self.user, passwd=self.password)
        self.is_connected = True

    def _ensure_connection(self):
        # Must be called within a lock or by a method that holds the lock
        if not self.is_connected or not self.ftp:
            try:
                self._perform_connect()
            except Exception as e:
                raise Exception(f"Reconnection failed: {e}")
        else:
            try:
                self.ftp.voidcmd("NOOP")
            except:
                try:
                    self._perform_connect()
                except Exception as e:
                    raise Exception(f"Reconnection failed: {e}")

    def list_files(self):
        threading.Thread(target=self._list_files_thread, daemon=True).start()

    def _list_files_thread(self):
        with self.lock:
            try:
                self._ensure_connection()
                self._list_files_internal()
            except Exception as e:
                self._emit("error", f"Failed to list files: {e}")

    def _list_files_internal(self):
        # Helper method, assumes lock is held and connection is valid
        files = []
        filenames = self.ftp.nlst()
        self._emit("file_list", filenames)

    def upload_file(self, file_path):
        threading.Thread(target=self._upload_thread, args=(file_path,), daemon=True).start()

    def _upload_thread(self, file_path):
        with self.lock:
            try:
                self._ensure_connection()
                filename = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                
                with open(file_path, 'rb') as f:
                    bytes_sent = 0
                    
                    def callback(data):
                        nonlocal bytes_sent
                        bytes_sent += len(data)
                        progress = int((bytes_sent / file_size) * 100)
                        self._emit("upload_progress", progress)

                    self.ftp.storbinary(f'STOR {filename}', f, 8192, callback)
                
                self._emit("upload_finished", filename)
                self._list_files_internal() # Refresh list
            except Exception as e:
                self._emit("error", f"Upload failed: {e}")

    def delete_file(self, filename):
        threading.Thread(target=self._delete_thread, args=(filename,), daemon=True).start()

    def _delete_thread(self, filename):
        with self.lock:
            try:
                self._ensure_connection()
                self.ftp.delete(filename)
                self._emit("delete_finished", filename)
                self._list_files_internal() # Refresh list
            except Exception as e:
                self._emit("error", f"Delete failed: {e}")

    def disconnect(self):
        threading.Thread(target=self._disconnect_thread, daemon=True).start()

    def _disconnect_thread(self):
        with self.lock:
            if self.ftp:
                try:
                    self.ftp.quit()
                except:
                    try:
                        self.ftp.close()
                    except:
                        pass
            self.ftp = None
            self.is_connected = False
            self._emit("disconnected", "Disconnected")
