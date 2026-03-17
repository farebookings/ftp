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

class FTPClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cliente FTP Fantuber")
        self.root.geometry("1300x750")
        self.root.minsize(1000, 600)

        self.upload_queue = []
        self.is_uploading = False
        self.file_checks = {}
        self.settings_file = self._get_settings_path()
        self.file_checkboxes = []
        
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

        # Header
        header_frame = ctk.CTkFrame(self.main_frame, fg_color=("#f0f0f0", "#1a1a1a"))
        header_frame.pack(fill=ctk.X, padx=0, pady=0)
        
        header_label = ctk.CTkLabel(header_frame, text="📁 Cliente FTP Fantuber", 
                                    font=ctk.CTkFont(size=32, weight="bold"))
        header_label.pack(padx=20, pady=15)

        # Separador
        separator = ctk.CTkLabel(self.main_frame, text="", height=2, 
                                 fg_color=("#e0e0e0", "#2a2a2a"))
        separator.pack(fill=ctk.X)

        # Content area
        content_frame = ctk.CTkFrame(self.main_frame)
        content_frame.pack(fill=ctk.BOTH, expand=True, padx=12, pady=12)

        # Connection Panel
        self._create_connection_panel(content_frame)

        # Left and Right sections
        sections_frame = ctk.CTkFrame(content_frame)
        sections_frame.pack(fill=ctk.BOTH, expand=True, pady=(15, 0))

        # Left: File List
        self._create_file_list_panel(sections_frame)

        # Right: Upload Area
        self._create_upload_panel(sections_frame)

        # Status bar at bottom
        self._create_status_bar()

    def _create_connection_panel(self, parent):
        conn_frame = ctk.CTkFrame(parent, fg_color=("gray85", "gray20"))
        conn_frame.pack(fill=ctk.X, pady=(0, 15))

        title_label = ctk.CTkLabel(conn_frame, text="🔌 Conexión", 
                                   font=ctk.CTkFont(size=16, weight="bold"))
        title_label.pack(anchor="w", padx=15, pady=(10, 8))

        # Input fields grid
        inputs_frame = ctk.CTkFrame(conn_frame, fg_color="transparent")
        inputs_frame.pack(fill=ctk.X, padx=15, pady=(0, 15))

        # Row 1: Host, User, Password, Button
        ctk.CTkLabel(inputs_frame, text="Servidor:", font=ctk.CTkFont(size=14)).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.host_entry = ctk.CTkEntry(inputs_frame, placeholder_text="ejemplo.com", width=180)
        self.host_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        ctk.CTkLabel(inputs_frame, text="Usuario:", font=ctk.CTkFont(size=14)).grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.user_entry = ctk.CTkEntry(inputs_frame, placeholder_text="usuario", width=150)
        self.user_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=5)

        ctk.CTkLabel(inputs_frame, text="Contraseña:", font=ctk.CTkFont(size=14)).grid(row=0, column=4, sticky="w", padx=5, pady=5)
        self.pass_entry = ctk.CTkEntry(inputs_frame, placeholder_text="contraseña", show="*", width=150)
        self.pass_entry.grid(row=0, column=5, sticky="ew", padx=5, pady=5)

        self.connect_btn = ctk.CTkButton(inputs_frame, text="Conectar", command=self.connect_ftp, 
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        width=110, height=35)
        self.connect_btn.grid(row=0, column=6, padx=10, pady=5)

        # Status label
        self.status_label = ctk.CTkLabel(conn_frame, text="● Desconectado", 
                                         text_color=("red", "red"),
                                         font=ctk.CTkFont(size=14))
        self.status_label.pack(anchor="w", padx=15, pady=(0, 10))

        inputs_frame.columnconfigure(1, weight=1)
        inputs_frame.columnconfigure(3, weight=1)
        inputs_frame.columnconfigure(5, weight=1)

    def _create_file_list_panel(self, parent):
        list_frame = ctk.CTkFrame(parent, fg_color=("gray85", "gray20"))
        list_frame.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True, padx=(0, 8))

        # Title
        title_label = ctk.CTkLabel(list_frame, text="📋 Archivos en el Servidor", 
                                   font=ctk.CTkFont(size=14, weight="bold"))
        title_label.pack(anchor="w", padx=15, pady=(12, 8))

        # Control buttons frame
        controls_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        controls_frame.pack(fill=ctk.X, padx=15, pady=(0, 10))

        self.select_all_var = tk.BooleanVar()
        select_all_checkbox = ctk.CTkCheckBox(controls_frame, text="Seleccionar Todo",
                                             variable=self.select_all_var,
                                             command=self.toggle_select_all,
                                             font=ctk.CTkFont(size=14))
        select_all_checkbox.pack(side=ctk.LEFT)

        self.delete_btn = ctk.CTkButton(controls_frame, text="🗑️  Eliminar",
                                        command=self.delete_selected_files,
                                        state=ctk.DISABLED,
                                        fg_color=("#e74c3c", "#c0392b"),
                                        hover_color=("#c0392b", "#a93226"),
                                        text_color="white",
                                        font=ctk.CTkFont(size=14),
                                        width=100)
        self.delete_btn.pack(side=ctk.RIGHT)

        # Scrollable frame for file list
        scroll_frame = ctk.CTkScrollableFrame(list_frame, fg_color="transparent")
        scroll_frame.pack(fill=ctk.BOTH, expand=True, padx=15, pady=(0, 15))

        self.file_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        self.file_frame.pack(fill=ctk.BOTH, expand=True)

    def _create_upload_panel(self, parent):
        upload_frame = ctk.CTkFrame(parent, fg_color=("gray85", "gray20"))
        upload_frame.pack(side=ctk.RIGHT, fill=ctk.BOTH, expand=True, padx=(8, 0))

        # Title
        title_label = ctk.CTkLabel(upload_frame, text="⬆️  Subir Archivos", 
                                   font=ctk.CTkFont(size=14, weight="bold"))
        title_label.pack(anchor="w", padx=15, pady=(12, 10))

        # Drop Zone - usando Tkinter estándar para compatibilidad con tkinterdnd2
        inner_frame = ctk.CTkFrame(upload_frame)
        inner_frame.pack(fill=ctk.BOTH, expand=True, padx=15, pady=(0, 10))
        
        drop_frame = tk.Frame(inner_frame, bg="#4a9eff", relief=tk.RAISED, bd=2)
        drop_frame.pack(fill=tk.BOTH, expand=True)
        drop_frame.drop_target_register(DND_FILES)
        drop_frame.dnd_bind('<<Drop>>', self.on_drop)
        
        drop_label = tk.Label(drop_frame, text="📥 Arrastra y suelta\narchivos aquí", 
                              font=("Segoe UI", 16, "bold"),
                              bg="#4a9eff", fg="white")
        drop_label.pack(expand=True)
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind('<<Drop>>', self.on_drop)

        # Select Button
        self.select_files_btn = ctk.CTkButton(upload_frame, text="📂 Seleccionar Archivos...", 
                                             command=self.open_file_dialog,
                                             font=ctk.CTkFont(size=14),
                                             height=35)
        self.select_files_btn.pack(fill=ctk.X, padx=15, pady=(0, 10))

        # Progress Bar
        progress_label = ctk.CTkLabel(upload_frame, text="Progreso de Subida:", 
                                     font=ctk.CTkFont(size=14))
        progress_label.pack(anchor="w", padx=15, pady=(5, 0))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(upload_frame, variable=self.progress_var)
        self.progress_bar.pack(fill=ctk.X, padx=15, pady=(3, 5))

        # Progress percentage
        self.progress_label = ctk.CTkLabel(upload_frame, text="0%", 
                                          font=ctk.CTkFont(size=11))
        self.progress_label.pack(anchor="e", padx=15, pady=(0, 15))

    def _create_status_bar(self):
        status_frame = ctk.CTkFrame(self.main_frame, fg_color=("#f0f0f0", "#1a1a1a"), height=40)
        status_frame.pack(side=ctk.BOTTOM, fill=ctk.X, padx=0, pady=0)

        self.status_bar_label = ctk.CTkLabel(status_frame, text="Listo", 
                                            font=ctk.CTkFont(size=12),
                                            text_color=("gray", "gray"))
        self.status_bar_label.pack(anchor="w", padx=15, pady=8)

    def handle_worker_event(self, event_type, data):
        self.root.after(0, lambda: self._process_event(event_type, data))

    def _process_event(self, event_type, data):
        if event_type == "connected":
            self.status_label.configure(text="● Conectado", text_color=("green", "green"))
            self.status_bar_label.configure(text=f"✓ Conectado: {data}")
            self.connect_btn.configure(text="Desconectar")
            self.connect_btn.configure(state=ctk.NORMAL)
            self.delete_btn.configure(state=ctk.NORMAL)
        elif event_type == "disconnected":
            self.status_label.configure(text="● Desconectado", text_color=("red", "red"))
            self.status_bar_label.configure(text="Desconectado del servidor")
            self.connect_btn.configure(text="Conectar", state=ctk.NORMAL)
            self.delete_btn.configure(state=ctk.DISABLED)
            self.file_frame.pack_forget()
            self.file_frame = ctk.CTkFrame(self.file_frame.master, fg_color="transparent")
            self.file_checkboxes = []
        elif event_type == "connection_error":
            self.status_label.configure(text="● Error", text_color=("red", "red"))
            self.status_bar_label.configure(text=f"Error de conexión: {data}")
            self.connect_btn.configure(text="Conectar", state=ctk.NORMAL)
            messagebox.showerror("Error de Conexión", data)
        elif event_type == "file_list":
            self.update_file_list(data)
        elif event_type == "upload_progress":
            self.progress_var.set(data / 100)
            self.progress_label.configure(text=f"{int(data)}%")
        elif event_type == "upload_finished":
            self.status_bar_label.configure(text=f"✓ Subida completada: {data}")
            self.is_uploading = False
            # Refrescar la lista de archivos después de la subida
            self.worker.list_files()
            if not self.upload_queue:
                self.progress_var.set(0)
                self.progress_label.configure(text="0%")
                messagebox.showinfo("Éxito", "Todos los archivos se han subido correctamente.")
            else:
                self.process_queue()
        elif event_type == "delete_finished":
            self.status_bar_label.configure(text=f"✓ Archivo eliminado: {data}")
            # Refrescar la lista de archivos después de la eliminación
            self.worker.list_files()
        elif event_type == "error":
            self.status_bar_label.configure(text=f"✗ Error: {data}")
            self.is_uploading = False
            if self.upload_queue:
                if messagebox.askyesno("Error en cola", f"Ocurrió un error:\n{data}\n\n¿Desea continuar con el resto?"):
                    self.process_queue()
                else:
                    self.upload_queue.clear()
                    self.progress_var.set(0)
                    self.progress_label.configure(text="0%")
            else:
                if "Delete failed" not in str(data):
                    messagebox.showerror("Error", data)

    def connect_ftp(self):
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

        try:
            with open("debug_log.txt", "a") as f:
                f.write(f"[CONNECT] Host: {host}, User: {user}\n")
        except:
            pass

        self.save_settings()
        self.connect_btn.configure(state=ctk.DISABLED)
        self.status_label.configure(text="● Conectando...", text_color=("orange", "orange"))
        self.status_bar_label.configure(text="Conectando al servidor...")
        self.worker.connect_to_server(host, user, pwd)

    def update_file_list(self, files):
        # Clear existing checkboxes
        for widget in self.file_frame.winfo_children():
            widget.destroy()
        self.file_checkboxes = []
        self.select_all_var.set(False)

        if not files:
            empty_label = ctk.CTkLabel(self.file_frame, text="No hay archivos en el servidor",
                                      font=ctk.CTkFont(size=13),
                                      text_color=("gray", "gray"))
            empty_label.pack(pady=20)
            return

        for filename in files:
            var = tk.BooleanVar()
            checkbox = ctk.CTkCheckBox(self.file_frame, text=filename, variable=var,
                                       font=ctk.CTkFont(size=11))
            checkbox.pack(anchor="w", pady=3, padx=5)
            self.file_checkboxes.append((checkbox, var, filename))

        try:
            with open("debug_log.txt", "a") as f:
                f.write(f"[LIST] {len(files)} archivos listados\n")
        except:
            pass

    def toggle_select_all(self):
        state = self.select_all_var.get()
        for _, var, _ in self.file_checkboxes:
            var.set(state)

    def open_file_dialog(self):
        if self.connect_btn.cget("text") != "Desconectar":
            messagebox.showwarning("No conectado", "Primero debes conectarte al servidor FTP.")
            return

        files = filedialog.askopenfilenames(title="Seleccionar archivos para subir")
        if files:
            self.add_to_queue(list(files))

    def delete_selected_files(self):
        files_to_delete = [filename for _, var, filename in self.file_checkboxes if var.get()]
        
        if not files_to_delete:
            messagebox.showinfo("Info", "No hay archivos seleccionados para eliminar")
            return

        if messagebox.askyesno("Confirmar", f"¿Estás seguro de eliminar {len(files_to_delete)} archivo(s)?"):
            self.status_bar_label.configure(text=f"Eliminando {len(files_to_delete)} archivo(s)...")
            for f in files_to_delete:
                self.worker.delete_file(f)

    def on_drop(self, event):
        if self.connect_btn.cget("text") != "Desconectar":
            messagebox.showwarning("No conectado", "Primero debes conectarte al servidor FTP.")
            return
        
        # Procesar los archivos arrastrados
        files = self.root.tk.splitlist(event.data)
        # Filtrar solo archivos válidos (no directorios)
        valid_files = [f.replace('{', '').replace('}', '') for f in files if os.path.isfile(f.replace('{', '').replace('}', ''))]
        
        if valid_files:
            self.add_to_queue(valid_files)
        else:
            messagebox.showwarning("Archivos inválidos", "Por favor arrastra solo archivos, no directorios.")

    def add_to_queue(self, files):
        self.upload_queue.extend(files)
        self.status_bar_label.configure(text=f"Añadidos {len(files)} archivo(s). Total en cola: {len(self.upload_queue)}")
        self.process_queue()

    def process_queue(self):
        if self.is_uploading or not self.upload_queue:
            return
        
        file_path = self.upload_queue.pop(0)
        self.is_uploading = True
        self.progress_var.set(0)
        self.progress_label.configure(text="0%")
        filename = os.path.basename(file_path)
        self.status_bar_label.configure(text=f"Subiendo: {filename} (En cola: {len(self.upload_queue)})")
        self.worker.upload_file(file_path)

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

                with open("debug_log.txt", "a") as f:
                    f.write(f"[LOAD] Configuración cargada desde {self.settings_file}\n")
            except Exception as e:
                try:
                    with open("debug_log.txt", "a") as f:
                        f.write(f"[ERROR] Al cargar configuración: {e}\n")
                except:
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
