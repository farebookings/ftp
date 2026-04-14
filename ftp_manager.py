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
        self.is_connecting = False
        
        # Credentials
        self.host = None
        self.user = None
        self.password = None
        
        # Timeout settings
        self.timeout = 60  # Aumentado a 60 segundos
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        
        # Configuración de reintentos por archivo
        self.max_retries_per_file = 3
        
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
            for _ in range(30):
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

    def _get_remote_file_size(self, filename):
        """Obtener el tamaño de un archivo remoto"""
        try:
            # Intentar obtener el tamaño usando SIZE
            size = self.ftp.size(filename)
            return size if size is not None else 0
        except:
            return 0

    def _upload_with_resume(self, file_path, filename, index, total, retry_count=0):
        """Subir archivo con soporte para reanudación"""
        try:
            file_size = os.path.getsize(file_path)
            remote_size = self._get_remote_file_size(filename)
            
            # Determinar desde dónde reanudar
            resume_position = 0
            if remote_size > 0 and remote_size < file_size:
                resume_position = remote_size
                self._emit("upload_progress", {
                    "progress": int((resume_position / file_size) * 100),
                    "index": index,
                    "total": total,
                    "filename": filename,
                    "status": "resuming"
                })
                self._emit("retrying", f"Reanudando subida de {filename} desde {self._format_size(resume_position)}")
            
            with open(file_path, 'rb') as f:
                # Saltar a la posición donde se quedó
                if resume_position > 0:
                    f.seek(resume_position)
                
                bytes_sent = resume_position
                last_update = time.time()
                last_activity = time.time()
                stalled_count = 0
                
                def callback(data):
                    nonlocal bytes_sent, last_update, last_activity, stalled_count
                    bytes_sent += len(data)
                    last_activity = time.time()
                    stalled_count = 0  # Resetear contador de estancamiento
                    
                    now = time.time()
                    if now - last_update >= 0.5:  # Actualizar cada 500ms
                        progress = int((bytes_sent / file_size) * 100)
                        self._emit("upload_progress", {
                            "progress": progress,
                            "index": index,
                            "total": total,
                            "filename": filename,
                            "uploaded": self._format_size(bytes_sent),
                            "total_size": self._format_size(file_size),
                            "speed": self._calculate_speed(bytes_sent - resume_position, now - last_update) if bytes_sent > resume_position else "0 KB/s"
                        })
                        last_update = now
                
                # Usar un timeout más largo para archivos grandes
                if resume_position > 0:
                    # Usar REST para reanudar la transferencia
                    self.ftp.voidcmd(f"REST {resume_position}")
                
                # Iniciar la transferencia con callback de monitoreo
                self.ftp.storbinary(f'STOR {filename}', f, 8192, callback)
            
            # Transferencia completada exitosamente
            self._emit("upload_finished", {
                "filename": filename,
                "index": index,
                "total": total
            })
            
            # Refrescar lista
            self._do_list()
            return True
            
        except (socket.timeout, socket.error, error_temp, ConnectionError) as e:
            # Error de conexión - intentar reanudar
            error_msg = str(e)
            self.is_connected = False
            
            if retry_count < self.max_retries_per_file:
                self._emit("reconnecting", f"Error en transferencia, reintentando ({retry_count + 1}/{self.max_retries_per_file})...")
                time.sleep(2)  # Esperar antes de reintentar
                
                # Intentar reconectar
                if self._ensure_connection():
                    self._emit("retrying", f"Reanudando {filename}...")
                    # Reintentar con resume
                    return self._upload_with_resume(file_path, filename, index, total, retry_count + 1)
                else:
                    self._emit("error", f"No se pudo reconectar para reanudar {filename}")
                    return False
            else:
                self._emit("error", f"Error después de {self.max_retries_per_file} reintentos: {error_msg}")
                return False
                
        except Exception as e:
            self._emit("error", f"Error en transferencia: {str(e)}")
            return False

    def _format_size(self, size_bytes):
        """Formatear tamaño de archivo para mostrar"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def _calculate_speed(self, bytes_transferred, elapsed_time):
        """Calcular velocidad de transferencia"""
        if elapsed_time <= 0:
            return "0 KB/s"
        speed = bytes_transferred / elapsed_time  # bytes por segundo
        if speed < 1024:
            return f"{speed:.0f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed / 1024:.1f} KB/s"
        else:
            return f"{speed / (1024 * 1024):.1f} MB/s"

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
            self._emit("file_list", files)
        except (error_perm, error_temp, error_reply, socket.error) as e:
            self.is_connected = False
            self._emit("error", f"List failed: Connection lost - {str(e)}")
        except Exception as e:
            self._emit("error", f"List failed: {str(e)}")

    def _do_upload(self, params):
        """Ejecutar subida de archivo con reanudación automática"""
        file_path, index, total = params
        
        if not os.path.exists(file_path):
            self._emit("error", f"File not found: {file_path}")
            return
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        self._emit("upload_started", {
            "filename": filename,
            "index": index,
            "total": total,
            "size": file_size,
            "size_formatted": self._format_size(file_size)
        })
        
        # Usar el método con soporte para reanudación
        success = self._upload_with_resume(file_path, filename, index, total)
        
        if not success:
            self._emit("error", f"Upload failed for {filename} after multiple attempts")

    def _do_delete(self, filename):
        """Ejecutar eliminación de archivo"""
        if not self._ensure_connection():
            self._emit("error", f"Delete failed: Not connected")
            return
        
        try:
            self.ftp.delete(filename)
            self._emit("delete_finished", filename)
            self._do_list()
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