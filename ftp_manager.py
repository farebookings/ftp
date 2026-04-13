import os
import threading
import time
import queue
from ftplib import FTP, error_perm, error_temp, error_reply
import socket
from dataclasses import dataclass
from typing import Optional, Callable

@dataclass
class FTPCommand:
    """Comando FTP para la cola"""
    type: str  # 'connect', 'list', 'upload', 'delete', 'disconnect'
    data: any = None
    callback: Optional[Callable] = None

class FTPWorker:
    def __init__(self, callback_handler):
        self.callback_handler = callback_handler
        self.command_queue = queue.Queue()
        self.is_running = True
        self.ftp = None
        self.is_connected = False
        self.is_connecting = False  # Nuevo: evitar reconexiones múltiples
        
        # Credentials
        self.host = None
        self.user = None
        self.password = None
        
        # Timeout settings
        self.timeout = 30
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        
        # Iniciar el worker thread
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def _emit(self, event_type, data=None):
        """Emitir evento de forma segura"""
        if self.callback_handler:
            try:
                self.callback_handler(event_type, data)
            except Exception as e:
                print(f"Error emitting event: {e}")

    def _ensure_connection(self):
        """Asegurar que hay una conexión activa, reconectando si es necesario"""
        if not self.is_connected or not self._check_connection():
            if self.host and self.user and self.password:
                self._emit("reconnecting", "Conexión perdida, reconectando...")
                return self._do_reconnect()
            return False
        return True

    def _do_reconnect(self):
        """Reconectar al servidor FTP"""
        if self.is_connecting:
            # Esperar a que termine la reconexión actual
            for _ in range(30):  # Esperar hasta 3 segundos
                if not self.is_connecting:
                    break
                time.sleep(0.1)
            return self.is_connected
        
        self.is_connecting = True
        try:
            # Cerrar conexión existente si la hay
            if self.ftp:
                try:
                    self.ftp.quit()
                except:
                    try:
                        self.ftp.close()
                    except:
                        pass
            
            # Intentar reconectar
            self.ftp = FTP()
            self.ftp.connect(self.host, timeout=self.timeout)
            self.ftp.login(user=self.user, passwd=self.password)
            self.ftp.set_pasv(True)
            self.is_connected = True
            self.reconnect_attempts = 0
            self._emit("connected", f"Reconectado a {self.host}")
            return True
            
        except Exception as e:
            self.is_connected = False
            self.reconnect_attempts += 1
            self._emit("connection_error", f"Reconexión fallida: {str(e)}")
            return False
        finally:
            self.is_connecting = False

    def _process_queue(self):
        """Procesar comandos FTP en orden (un solo hilo)"""
        while self.is_running:
            try:
                # Esperar por un comando con timeout para poder verificar is_running
                try:
                    cmd = self.command_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Procesar el comando
                if cmd.type == 'connect':
                    self._do_connect(cmd.data)
                elif cmd.type == 'list':
                    self._do_list()
                elif cmd.type == 'upload':
                    self._do_upload(cmd.data)
                elif cmd.type == 'delete':
                    self._do_delete(cmd.data)
                elif cmd.type == 'disconnect':
                    self._do_disconnect()
                
                # Marcar como completado
                self.command_queue.task_done()
                
            except Exception as e:
                print(f"Error processing command: {e}")
                self._emit("error", f"Worker error: {str(e)}")

    def _do_connect(self, credentials):
        """Ejecutar conexión"""
        self.host, self.user, self.password = credentials
        self.is_connecting = True
        
        try:
            # Cerrar conexión existente si la hay
            if self.ftp:
                try:
                    self.ftp.quit()
                except:
                    pass
            
            # Nueva conexión
            self.ftp = FTP()
            self.ftp.connect(self.host, timeout=self.timeout)
            self.ftp.login(user=self.user, passwd=self.password)
            self.ftp.set_pasv(True)
            self.is_connected = True
            self.reconnect_attempts = 0
            self._emit("connected", f"Connected to {self.host}")
            
            # Listar archivos automáticamente
            self._do_list()
            
        except socket.timeout:
            self.is_connected = False
            self._emit("connection_error", "Connection timeout")
        except Exception as e:
            self.is_connected = False
            self._emit("connection_error", str(e))
        finally:
            self.is_connecting = False

    def _do_list(self):
        """Ejecutar listado de archivos"""
        # Intentar reconectar si es necesario
        if not self._ensure_connection():
            self._emit("error", "List failed: Not connected")
            return
        
        try:
            files = self.ftp.nlst()
            # Filtrar directorios (simple)
            valid_files = []
            for f in files:
                if not self._is_directory_safe(f):
                    valid_files.append(f)
            self._emit("file_list", valid_files)
        except (error_perm, error_temp, error_reply, socket.error) as e:
            # Error de conexión, marcar como desconectado
            self.is_connected = False
            self._emit("error", f"List failed: Connection lost - {str(e)}")
        except Exception as e:
            self._emit("error", f"List failed: {str(e)}")

    def _do_upload(self, params):
        """Ejecutar subida de archivo con reconexión automática"""
        file_path, index, total = params
        
        # Intentar reconectar si es necesario
        if not self._ensure_connection():
            self._emit("error", f"Upload failed: Not connected")
            return
        
        try:
            filename = os.path.basename(file_path)
            
            if not os.path.exists(file_path):
                raise Exception(f"File not found: {file_path}")
            
            file_size = os.path.getsize(file_path)
            
            with open(file_path, 'rb') as f:
                bytes_sent = 0
                last_update = time.time()
                
                def callback(data):
                    nonlocal bytes_sent, last_update
                    bytes_sent += len(data)
                    now = time.time()
                    if now - last_update >= 0.1:  # Actualizar cada 100ms
                        progress = int((bytes_sent / file_size) * 100)
                        self._emit("upload_progress", {
                            "progress": progress,
                            "index": index,
                            "total": total,
                            "filename": filename
                        })
                        last_update = now
                
                self.ftp.storbinary(f'STOR {filename}', f, 8192, callback)
            
            self._emit("upload_finished", {
                "filename": filename,
                "index": index,
                "total": total
            })
            
            # Refrescar lista
            self._do_list()
            
        except (error_perm, error_temp, error_reply, socket.error) as e:
            # Error de conexión, marcar como desconectado
            self.is_connected = False
            
            # Intentar reconectar una vez más
            self._emit("reconnecting", f"Connection lost during upload, attempting to reconnect...")
            if self._ensure_connection():
                # Reintentar la subida
                self._emit("retrying", f"Retrying upload for {os.path.basename(file_path)}")
                self._do_upload(params)  # Reintentar recursivamente
            else:
                self._emit("error", f"Upload failed for {os.path.basename(file_path)}: Connection lost and reconnection failed")
        except Exception as e:
            self._emit("error", f"Upload failed for {os.path.basename(file_path)}: {str(e)}")

    def _do_delete(self, filename):
        """Ejecutar eliminación de archivo"""
        # Intentar reconectar si es necesario
        if not self._ensure_connection():
            self._emit("error", f"Delete failed: Not connected")
            return
        
        try:
            self.ftp.delete(filename)
            self._emit("delete_finished", filename)
            self._do_list()  # Refrescar lista
        except (error_perm, error_temp, error_reply, socket.error) as e:
            self.is_connected = False
            self._emit("error", f"Delete failed for {filename}: Connection lost")
        except Exception as e:
            self._emit("error", f"Delete failed for {filename}: {str(e)}")

    def _do_disconnect(self):
        """Ejecutar desconexión"""
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
        self.is_connecting = False
        self._emit("disconnected", "Disconnected")

    def _check_connection(self):
        """Verificar conexión activa"""
        if not self.is_connected or not self.ftp:
            return False
        try:
            self.ftp.voidcmd("NOOP")
            return True
        except:
            self.is_connected = False
            return False

    def _is_directory_safe(self, path):
        """Verificar si es directorio sin cambiar directorio actual"""
        try:
            # Intentar obtener información del archivo
            # Si no hay excepción, probablemente es un archivo
            # Esto es más seguro que cambiar de directorio
            return False  # Por ahora asumimos que no es directorio
        except:
            return False

    # Métodos públicos (agregan comandos a la cola)
    def connect_to_server(self, host, user, password):
        self.command_queue.put(FTPCommand('connect', (host, user, password)))

    def list_files(self):
        self.command_queue.put(FTPCommand('list'))

    def upload_file(self, file_path, index=None, total=None):
        self.command_queue.put(FTPCommand('upload', (file_path, index, total)))

    def delete_file(self, filename):
        self.command_queue.put(FTPCommand('delete', filename))

    def disconnect(self):
        self.command_queue.put(FTPCommand('disconnect'))

    def stop(self):
        """Detener el worker"""
        self.is_running = False