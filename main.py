import sys
import os
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import configparser
from ftp_manager import FTPWorker
from tkinterdnd2 import DND_FILES, TkinterDnD

# Configurar tema y color
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class DraggableFileList:
    """Widget para lista de archivos con drag & drop para reordenar"""
    def __init__(self, parent, on_order_changed=None, on_file_removed=None):
        self.parent = parent
        self.on_order_changed = on_order_changed
        self.on_file_removed = on_file_removed  # Nuevo callback para cuando se elimina un archivo
        self.files = []
        self.file_frames = []
        self.drag_start_index = None
        self.drag_over_index = None
        self.is_dragging = False
        
        # Frame contenedor principal
        self.container = ctk.CTkFrame(parent, fg_color="transparent")
        self.container.pack(fill=ctk.BOTH, expand=True)
        
        # Scrollable frame
        self.scroll_frame = ctk.CTkScrollableFrame(self.container, fg_color=("gray90", "gray18"))
        self.scroll_frame.pack(fill=ctk.BOTH, expand=True)
        
        # Canvas interno para los items
        self.items_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.items_frame.pack(fill=ctk.BOTH, expand=True)
        
    def add_file(self, file_path):
        """Añadir un archivo a la lista"""
        self.files.append(file_path)
        self.refresh_list()
        
    def add_files(self, file_paths):
        """Añadir múltiples archivos a la lista"""
        self.files.extend(file_paths)
        self.refresh_list()
        
    def remove_file(self, index):
        """Eliminar un archivo de la lista por índice"""
        if 0 <= index < len(self.files):
            del self.files[index]
            self.refresh_list()
            # Llamar al callback cuando se elimina un archivo
            if self.on_file_removed:
                self.on_file_removed(len(self.files))
            
    def clear(self):
        """Limpiar toda la lista"""
        self.files.clear()
        self.refresh_list()
        if self.on_file_removed:
            self.on_file_removed(0)
        
    def get_files(self):
        """Obtener la lista de archivos en el orden actual"""
        return self.files.copy()
        
    def get_file_count(self):
        """Obtener número de archivos"""
        return len(self.files)
        
    def refresh_list(self):
        """Refrescar la interfaz de la lista"""
        # Limpiar frames existentes
        for frame in self.file_frames:
            try:
                frame.destroy()
            except:
                pass
        self.file_frames.clear()
        
        if not self.files:
            empty_label = ctk.CTkLabel(self.items_frame, text="No hay archivos en la cola\nArrastra archivos aquí", 
                                      font=ctk.CTkFont(size=18),
                                      text_color=("gray", "gray"))
            empty_label.pack(pady=60)
            self.file_frames.append(empty_label)
            return
            
        # Crear frames para cada archivo
        for i, file_path in enumerate(self.files):
            filename = os.path.basename(file_path)
            frame = ctk.CTkFrame(self.items_frame, fg_color=("gray85", "gray20"), corner_radius=8)
            frame.pack(fill=ctk.X, pady=5, padx=5)
            
            # Número de orden
            number_label = ctk.CTkLabel(frame, text=f"{i+1}.", 
                                       font=ctk.CTkFont(size=20, weight="bold"),
                                       width=60)
            number_label.pack(side=tk.LEFT, padx=(15, 5), pady=12)
            
            # Icono de arrastre
            drag_label = ctk.CTkLabel(frame, text="⋮⋮", 
                                     font=ctk.CTkFont(size=24),
                                     cursor="fleur",
                                     width=50)
            drag_label.pack(side=tk.LEFT, padx=5)
            
            # Bindings para el drag label
            drag_label.bind("<Button-1>", lambda e, idx=i: self.start_drag(e, idx))
            drag_label.bind("<B1-Motion>", lambda e, idx=i: self.on_drag(e, idx))
            drag_label.bind("<ButtonRelease-1>", lambda e, idx=i: self.end_drag(e, idx))
            
            # Nombre del archivo
            name_label = ctk.CTkLabel(frame, text=filename, 
                                     font=ctk.CTkFont(size=16),
                                     anchor="w")
            name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)
            
            # Botón eliminar
            delete_btn = ctk.CTkButton(frame, text="✕", width=40, height=40,
                                      fg_color="transparent",
                                      hover_color=("#e74c3c", "#c0392b"),
                                      text_color=("gray", "gray"),
                                      font=ctk.CTkFont(size=20),
                                      command=lambda idx=i: self.remove_file(idx))
            delete_btn.pack(side=tk.RIGHT, padx=15)
            
            # Guardar referencia
            frame.file_index = i
            frame.file_path = file_path
            frame.drag_label = drag_label
            self.file_frames.append(frame)
            
    def start_drag(self, event, index):
        """Iniciar el arrastre"""
        self.drag_start_index = index
        self.drag_over_index = index
        self.is_dragging = True
        if index < len(self.file_frames):
            self.file_frames[index].configure(fg_color=("gray70", "gray35"))
        
    def on_drag(self, event, index):
        """Durante el arrastre - detectar sobre qué elemento estamos"""
        if not self.is_dragging or self.drag_start_index is None:
            return
            
        # Obtener la posición del ratón
        mouse_y = event.y_root
        
        # Encontrar sobre qué frame está el ratón
        for i, frame in enumerate(self.file_frames):
            if i == self.drag_start_index:
                continue
            try:
                frame_y = frame.winfo_rooty()
                frame_height = frame.winfo_height()
                
                if frame_y <= mouse_y <= frame_y + frame_height:
                    if i != self.drag_over_index:
                        self.drag_over_index = i
                        frame.configure(fg_color=("gray75", "gray28"))
                        for j, f in enumerate(self.file_frames):
                            if j != self.drag_over_index and j != self.drag_start_index:
                                try:
                                    f.configure(fg_color=("gray85", "gray20"))
                                except:
                                    pass
                    break
            except:
                pass
        
    def end_drag(self, event, index):
        """Finalizar el arrastre y reordenar"""
        if self.is_dragging and self.drag_start_index is not None and self.drag_over_index is not None:
            if self.drag_start_index != self.drag_over_index:
                # Mover el elemento
                file_to_move = self.files.pop(self.drag_start_index)
                self.files.insert(self.drag_over_index, file_to_move)
                self.refresh_list()
                if self.on_order_changed:
                    self.on_order_changed()
        
        # Restaurar estilos
        for frame in self.file_frames:
            try:
                frame.configure(fg_color=("gray85", "gray20"))
            except:
                pass
            
        self.drag_start_index = None
        self.drag_over_index = None
        self.is_dragging = False


class FTPClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cliente FTP Fantuber")
        self.root.geometry("1200x750")
        self.root.minsize(1000, 600)

        self.is_uploading = False
        self.current_upload_index = 0
        self.total_uploads = 0
        self.settings_file = self._get_settings_path()
        
        self.worker = FTPWorker(self.handle_worker_event)
        
        self.init_ui()
        self.load_settings()

    def _get_settings_path(self):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(application_path, "settings.ini")

    def init_ui(self):
        # Main container
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=ctk.BOTH, expand=True, padx=0, pady=0)

        # Separador
        separator = ctk.CTkLabel(self.main_frame, text="", height=2, 
                                 fg_color=("#e0e0e0", "#2a2a2a"))
        separator.pack(fill=ctk.X)

        # Content area
        content_frame = ctk.CTkFrame(self.main_frame)
        content_frame.pack(fill=ctk.BOTH, expand=True, padx=15, pady=15)

        # Connection Panel
        self._create_connection_panel(content_frame)

        # Two column layout para cola y añadir archivos
        columns_frame = ctk.CTkFrame(content_frame)
        columns_frame.pack(fill=ctk.BOTH, expand=True, pady=(15, 0))

        # Left: Upload Queue (70%)
        left_frame = ctk.CTkFrame(columns_frame, fg_color=("gray85", "gray20"))
        left_frame.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True, padx=(0, 8))
        self._create_queue_panel(left_frame)

        # Right: Add Files (30%)
        right_frame = ctk.CTkFrame(columns_frame, fg_color=("gray85", "gray20"))
        right_frame.pack(side=ctk.RIGHT, fill=ctk.BOTH, expand=True, padx=(8, 0))
        self._create_upload_panel(right_frame)

        # Status bar at bottom
        self._create_status_bar()

    def _create_connection_panel(self, parent):
        conn_frame = ctk.CTkFrame(parent, fg_color=("gray85", "gray20"))
        conn_frame.pack(fill=ctk.X, pady=(0, 15))

        title_label = ctk.CTkLabel(conn_frame, text="🔌 Conexión", 
                                   font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(anchor="w", padx=15, pady=(10, 8))

        # Input fields grid
        inputs_frame = ctk.CTkFrame(conn_frame, fg_color="transparent")
        inputs_frame.pack(fill=ctk.X, padx=15, pady=(0, 15))

        ctk.CTkLabel(inputs_frame, text="Servidor:", font=ctk.CTkFont(size=18)).grid(row=0, column=0, sticky="w", padx=5, pady=8)
        self.host_entry = ctk.CTkEntry(inputs_frame, placeholder_text="ejemplo.com", width=200, font=ctk.CTkFont(size=16))
        self.host_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=8)

        ctk.CTkLabel(inputs_frame, text="Usuario:", font=ctk.CTkFont(size=18)).grid(row=0, column=2, sticky="w", padx=5, pady=8)
        self.user_entry = ctk.CTkEntry(inputs_frame, placeholder_text="usuario", width=170, font=ctk.CTkFont(size=16))
        self.user_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=8)

        ctk.CTkLabel(inputs_frame, text="Contraseña:", font=ctk.CTkFont(size=18)).grid(row=0, column=4, sticky="w", padx=5, pady=8)
        self.pass_entry = ctk.CTkEntry(inputs_frame, placeholder_text="contraseña", show="*", width=170, font=ctk.CTkFont(size=16))
        self.pass_entry.grid(row=0, column=5, sticky="ew", padx=5, pady=8)

        self.connect_btn = ctk.CTkButton(inputs_frame, text="Conectar", command=self.connect_ftp, 
                                        font=ctk.CTkFont(size=15, weight="bold"),
                                        width=120, height=40)
        self.connect_btn.grid(row=0, column=6, padx=10, pady=8)

        # Status label
        self.status_label = ctk.CTkLabel(conn_frame, text="● Desconectado", 
                                         text_color=("red", "red"),
                                         font=ctk.CTkFont(size=18))
        self.status_label.pack(anchor="w", padx=15, pady=(0, 10))

        inputs_frame.columnconfigure(1, weight=1)
        inputs_frame.columnconfigure(3, weight=1)
        inputs_frame.columnconfigure(5, weight=1)

    def _create_queue_panel(self, parent):
        # Title
        title_label = ctk.CTkLabel(parent, text="⏰ Cola de Subida", 
                                   font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(anchor="w", padx=15, pady=(12, 8))
        
        # Info label
        info_label = ctk.CTkLabel(parent, text="Arrastra los íconos ⋮⋮ para reordenar | Los archivos se subirán en este orden",
                                 font=ctk.CTkFont(size=14),
                                 text_color=("gray", "gray"))
        info_label.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Lista ordenable con callback para cuando se eliminan archivos
        self.queue_list = DraggableFileList(parent, 
                                           on_order_changed=self.on_queue_order_changed,
                                           on_file_removed=self.update_queue_count)
        
        # Botones de control de cola
        queue_controls = ctk.CTkFrame(parent, fg_color="transparent")
        queue_controls.pack(fill=ctk.X, padx=15, pady=(15, 15))
        
        self.clear_queue_btn = ctk.CTkButton(queue_controls, text="🗑️ Limpiar Cola",
                                            command=self.clear_queue,
                                            fg_color=("gray70", "gray30"),
                                            hover_color=("#e74c3c", "#c0392b"),
                                            font=ctk.CTkFont(size=15),
                                            width=130,
                                            height=45)
        self.clear_queue_btn.pack(side=ctk.LEFT, padx=5)
        
        self.upload_queue_btn = ctk.CTkButton(queue_controls, text="▶ Subir Todos",
                                             command=self.start_upload_queue,
                                             fg_color=("#2ecc71", "#27ae60"),
                                             hover_color=("#27ae60", "#229954"),
                                             font=ctk.CTkFont(size=16, weight="bold"),
                                             height=45,
                                             width=280)
        self.upload_queue_btn.pack(side=ctk.RIGHT, padx=5)

    def _create_upload_panel(self, parent):
        # Drop Zone
        inner_frame = ctk.CTkFrame(parent)
        inner_frame.pack(fill=ctk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        drop_frame = tk.Frame(inner_frame, bg="#00397A")
        drop_frame.pack(fill=tk.BOTH, expand=True)
        drop_frame.drop_target_register(DND_FILES)
        drop_frame.dnd_bind('<<Drop>>', self.on_drop)
        
        drop_label = tk.Label(drop_frame, text="📥 Arrastra y suelta\narchivos aquí", 
                              font=("Segoe UI", 16, "bold"),
                              bg="#00397A", fg="white")
        drop_label.pack(expand=True)
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind('<<Drop>>', self.on_drop)

        # Select Button
        self.select_files_btn = ctk.CTkButton(parent, text="📂 Seleccionar Archivos...", 
                                             command=self.open_file_dialog,
                                             font=ctk.CTkFont(size=16),
                                             height=50)
        self.select_files_btn.pack(fill=ctk.X, padx=15, pady=(0, 20))

        # Progress Bar
        progress_label = ctk.CTkLabel(parent, text="📊 Progreso de Subida:", 
                                     font=ctk.CTkFont(size=16))
        progress_label.pack(anchor="w", padx=15, pady=(10, 5))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(parent, variable=self.progress_var, height=15)
        self.progress_bar.pack(fill=ctk.X, padx=15, pady=(5, 5))

        # Progress percentage and info
        self.progress_label = ctk.CTkLabel(parent, text="0%", 
                                          font=ctk.CTkFont(size=15))
        self.progress_label.pack(anchor="e", padx=15)
        
        self.current_file_label = ctk.CTkLabel(parent, text="", 
                                              font=ctk.CTkFont(size=14),
                                              text_color=("gray", "gray"))
        self.current_file_label.pack(anchor="w", padx=15, pady=(10, 15))

    def _create_status_bar(self):
        status_frame = ctk.CTkFrame(self.main_frame, fg_color=("#f0f0f0", "#1a1a1a"), height=50)
        status_frame.pack(side=ctk.BOTTOM, fill=ctk.X, padx=0, pady=0)

        self.status_bar_label = ctk.CTkLabel(status_frame, text="✅ Listo", 
                                            font=ctk.CTkFont(size=15),
                                            text_color=("gray", "gray"))
        self.status_bar_label.pack(anchor="w", padx=15, pady=12)

    def update_queue_count(self, count):
        """Actualizar el contador de archivos en la cola en la barra de estado"""
        if count == 0:
            self.status_bar_label.configure(text="✅ Cola vacía")
        elif count == 1:
            self.status_bar_label.configure(text=f"📎 1 archivo en cola")
        else:
            self.status_bar_label.configure(text=f"📎 {count} archivos en cola")

    def on_queue_order_changed(self):
        """Callback cuando se reordena la cola"""
        count = self.queue_list.get_file_count()
        self.status_bar_label.configure(text=f"📌 Orden modificado - {count} archivos en cola")

    def handle_worker_event(self, event_type, data):
        self.root.after(0, lambda: self._process_event(event_type, data))

    def _process_event(self, event_type, data):
        if event_type == "connected":
            self.status_label.configure(text="● Conectado", text_color=("green", "green"))
            self.status_bar_label.configure(text=f"✅ Conectado: {data}")
            self.connect_btn.configure(text="Desconectar", state=ctk.NORMAL)
        elif event_type == "disconnected":
            self.status_label.configure(text="● Desconectado", text_color=("red", "red"))
            self.status_bar_label.configure(text="❌ Desconectado del servidor")
            self.connect_btn.configure(text="Conectar", state=ctk.NORMAL)
        elif event_type == "connection_error":
            self.status_label.configure(text="● Error", text_color=("red", "red"))
            self.status_bar_label.configure(text=f"⚠️ Error de conexión: {data}")
            self.connect_btn.configure(text="Conectar", state=ctk.NORMAL)
            messagebox.showerror("Error de Conexión", data)
        elif event_type == "reconnecting":
            # Nuevo: Mostrar estado de reconexión
            self.status_bar_label.configure(text=f"🔄 {data}")
            self.status_label.configure(text="● Reconectando...", text_color=("orange", "orange"))
            self.connect_btn.configure(state=ctk.DISABLED)
        elif event_type == "retrying":
            # Nuevo: Mostrar reintento de subida
            self.status_bar_label.configure(text=f"🔄 {data}")
        elif event_type == "upload_progress":
            if isinstance(data, dict):
                progress = data.get("progress", 0)
                current = data.get("index", 0)
                total = data.get("total", 0)
                filename = data.get("filename", "")
                
                self.progress_var.set(progress / 100)
                self.progress_label.configure(text=f"{int(progress)}%")
                self.current_file_label.configure(text=f"📤 Subiendo ({current+1}/{total}): {filename}")
        elif event_type == "upload_finished":
            if isinstance(data, dict):
                filename = data.get("filename", "")
                current_index = data.get("index", 0)
                total = data.get("total", 0)
                
                self.status_bar_label.configure(text=f"✅ Subida completada: {filename} ({current_index+1}/{total})")
                
                self.current_upload_index += 1
                
                if self.current_upload_index < self.total_uploads:
                    self.upload_next_in_queue()
                else:
                    self.is_uploading = False
                    self.progress_var.set(0)
                    self.progress_label.configure(text="0%")
                    self.current_file_label.configure(text="")
                    self.status_bar_label.configure(text="✅ Todas las subidas completadas")
                    messagebox.showinfo("Éxito", "Todos los archivos se han subido correctamente en el orden establecido.")
                    self.queue_list.clear()
        elif event_type == "error":
            self.status_bar_label.configure(text=f"❌ Error: {data}")
            # No desactivar is_uploading inmediatamente, permitir reconexión automática
            if "Connection lost" in str(data) and self.is_uploading:
                self.status_bar_label.configure(text=f"⚠️ {data} - Reconectando...")
            else:
                self.is_uploading = False
                if "Upload failed" in str(data):
                    if messagebox.askyesno("Error en subida", f"{data}\n\n¿Desea continuar con el siguiente archivo?"):
                        self.current_upload_index += 1
                        if self.current_upload_index < self.total_uploads:
                            self.upload_next_in_queue()
                    else:
                        self.is_uploading = False
                        self.progress_var.set(0)
                        self.progress_label.configure(text="0%")
                        self.current_file_label.configure(text="")
                else:
                    messagebox.showerror("Error", data)

    def connect_ftp(self):
        """Método para conectar o desconectar del servidor FTP"""
        if self.connect_btn.cget("text") == "Desconectar":
            self.status_label.configure(text="● Desconectando...", text_color=("orange", "orange"))
            self.connect_btn.configure(state=ctk.DISABLED)
            self.worker.disconnect()
            return

        host = self.host_entry.get().strip()
        user = self.user_entry.get().strip()
        pwd = self.pass_entry.get().strip()

        if host.lower().startswith("ftp://"):
            host = host[6:]

        if not host or not user or not pwd:
            messagebox.showwarning("Campos vacíos", "Por favor complete todos los campos")
            return

        self.save_settings()
        self.connect_btn.configure(state=ctk.DISABLED)
        self.status_label.configure(text="● Conectando...", text_color=("orange", "orange"))
        self.status_bar_label.configure(text="🔄 Conectando al servidor...")
        self.worker.connect_to_server(host, user, pwd)

    def open_file_dialog(self):
        if self.connect_btn.cget("text") != "Desconectar":
            messagebox.showwarning("No conectado", "Primero debes conectarte al servidor FTP.")
            return

        files = filedialog.askopenfilenames(title="Seleccionar archivos para subir")
        if files:
            self.add_to_queue(list(files))

    def on_drop(self, event):
        if self.connect_btn.cget("text") != "Desconectar":
            messagebox.showwarning("No conectado", "Primero debes conectarte al servidor FTP.")
            return
        
        try:
            files = self.root.tk.splitlist(event.data)
            valid_files = [f.replace('{', '').replace('}', '') for f in files if os.path.isfile(f.replace('{', '').replace('}', ''))]
            
            if valid_files:
                self.add_to_queue(valid_files)
            else:
                messagebox.showwarning("Archivos inválidos", "Por favor arrastra solo archivos, no directorios.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar archivos: {e}")

    def add_to_queue(self, files):
        """Añadir archivos a la cola (se añaden al final)"""
        for file_path in files:
            if file_path not in self.queue_list.get_files():
                self.queue_list.add_file(file_path)
        
        count = self.queue_list.get_file_count()
        self.update_queue_count(count)
        
        if count > 1:
            self.status_bar_label.configure(text=f"📎 {count} archivos en cola. Arrastra los íconos ⋮⋮ para reordenar.")

    def clear_queue(self):
        """Limpiar toda la cola"""
        if self.queue_list.get_file_count() > 0:
            if messagebox.askyesno("Limpiar Cola", "¿Estás seguro de que quieres limpiar toda la cola de subida?"):
                self.queue_list.clear()
                self.status_bar_label.configure(text="🗑️ Cola limpiada")

    def start_upload_queue(self):
        """Iniciar la subida de todos los archivos en la cola respetando el orden"""
        files = self.queue_list.get_files()
        
        if not files:
            messagebox.showinfo("Cola vacía", "No hay archivos en la cola para subir.")
            return
            
        if self.connect_btn.cget("text") != "Desconectar":
            messagebox.showwarning("No conectado", "Primero debes conectarte al servidor FTP.")
            return
            
        if self.is_uploading:
            messagebox.showinfo("Subida en progreso", "Ya hay una subida en curso. Espera a que termine.")
            return
            
        total = len(files)
        preview = "\n".join([f"{i+1}. {os.path.basename(f)}" for i, f in enumerate(files[:15])])
        if total > 15:
            preview += f"\n... y {total-15} más"
            
        if messagebox.askyesno("Confirmar Subida", 
                               f"📤 Se subirán {total} archivo(s) en el siguiente orden:\n\n{preview}\n\n¿Deseas continuar?"):
            
            self.is_uploading = True
            self.current_upload_index = 0
            self.total_uploads = total
            self.upload_next_in_queue()
    
    def upload_next_in_queue(self):
        """Subir el siguiente archivo en la cola"""
        files = self.queue_list.get_files()
        
        if self.current_upload_index >= len(files):
            self.is_uploading = False
            return
            
        file_path = files[self.current_upload_index]
        filename = os.path.basename(file_path)
        
        self.status_bar_label.configure(text=f"📤 Subiendo ({self.current_upload_index+1}/{self.total_uploads}): {filename}")
        self.progress_var.set(0)
        self.progress_label.configure(text="0%")
        self.current_file_label.configure(text=f"📤 Subiendo ({self.current_upload_index+1}/{self.total_uploads}): {filename}")
        
        self.worker.upload_file(file_path, self.current_upload_index, self.total_uploads)

    def load_settings(self):
        config = configparser.ConfigParser(interpolation=None)
        if os.path.exists(self.settings_file):
            try:
                config.read(self.settings_file)
                section = "General" if "General" in config else ("Credentials" if "Credentials" in config else None)
                
                if section:
                    self.host_entry.insert(0, config[section].get("host", ""))
                    self.user_entry.insert(0, config[section].get("user", ""))
                    self.pass_entry.insert(0, config[section].get("password", ""))
            except Exception as e:
                pass

    def save_settings(self):
        config = configparser.ConfigParser(interpolation=None)
        config["General"] = {
            "host": self.host_entry.get(),
            "user": self.user_entry.get(),
            "password": self.pass_entry.get()
        }
        try:
            with open(self.settings_file, "w") as f:
                config.write(f)
        except Exception as e:
            print(f"Error guardando configuración: {e}")


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = FTPClientApp(root)
    root.mainloop()