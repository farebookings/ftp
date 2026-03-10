import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinterdnd2 import DND_FILES, TkinterDnD
import configparser

from ftp_manager import FTPWorker

class FTPClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cliente FTP Fantuber")
        self.root.geometry("600x700")

        self.upload_queue = []
        self.is_uploading = False
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
        self.setup_styles()
        
        self.root.geometry("1000x700")
        
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_lbl = ttk.Label(main_frame, text="Cliente FTP Fantuber", style="Header.TLabel")
        header_lbl.pack(pady=(0, 20))

        # Connection Area
        conn_frame = ttk.LabelFrame(main_frame, text="Conexión", padding="15")
        conn_frame.pack(fill=tk.X, pady=5)

        # Grid layout with better spacing
        ttk.Label(conn_frame, text="Servidor:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.host_entry = ttk.Entry(conn_frame)
        self.host_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(conn_frame, text="Usuario:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.user_entry = ttk.Entry(conn_frame)
        self.user_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        ttk.Label(conn_frame, text="Contraseña:").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.pass_entry = ttk.Entry(conn_frame, show="*")
        self.pass_entry.grid(row=0, column=5, padx=5, pady=5, sticky="ew")

        self.connect_btn = ttk.Button(conn_frame, text="Conectar", command=self.connect_ftp, style="Accent.TButton")
        self.connect_btn.grid(row=0, column=6, padx=10, pady=5)
        
        conn_frame.columnconfigure(1, weight=3)
        conn_frame.columnconfigure(3, weight=2)
        conn_frame.columnconfigure(5, weight=2)

        # Content Container (Side by Side)
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=15)

        # --- LEFT SIDE: File List ---
        list_frame = ttk.LabelFrame(content_frame, text="Archivos en el servidor", padding="15")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Selection Controls
        sel_frame = ttk.Frame(list_frame)
        sel_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.select_all_var = tk.BooleanVar()
        self.select_all_cb = ttk.Checkbutton(sel_frame, text="Seleccionar Todos", variable=self.select_all_var, command=self.toggle_select_all)
        self.select_all_cb.pack(side=tk.LEFT)
        
        self.delete_btn = ttk.Button(sel_frame, text="Eliminar", command=self.delete_selected_files, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.RIGHT)

        # Treeview
        self.tree = ttk.Treeview(list_frame, columns=("filename", "status"), displaycolumns=(), show="tree", selectmode="none", height=15)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.tree.bind("<Button-1>", self.on_tree_click)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # --- RIGHT SIDE: Upload Area ---
        upload_frame = ttk.LabelFrame(content_frame, text="Subir Archivos", padding="15")
        upload_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # Drop Zone
        drop_container = ttk.Frame(upload_frame)
        drop_container.pack(fill=tk.BOTH, expand=True)
        
        self.drop_lbl = tk.Label(drop_container, text="\n\nArrastra y suelta\narchivos aquí\n\n", 
                                 bg="#e1f5fe", fg="#0277bd", relief="flat", borderwidth=0, font=("Segoe UI", 12, "bold"))
        self.drop_lbl.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.drop_lbl.drop_target_register(DND_FILES)
        self.drop_lbl.dnd_bind('<<Drop>>', self.on_drop)

        # Select Button
        self.select_files_btn = ttk.Button(upload_frame, text="O Seleccionar Archivos...", command=self.open_file_dialog)
        self.select_files_btn.pack(fill=tk.X, pady=5)

        # Progress Bar (Bottom of upload frame)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(upload_frame, variable=self.progress_var, maximum=100)
        # Initially hidden (pack_forget)

        # Status Bar
        self.status_var = tk.StringVar(value="Listo")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.FLAT, anchor=tk.W, background="#e0e0e0", padding=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_styles(self):
        style = ttk.Style()
        
        # Attempt to use 'clam' theme for better cross-platform look, or 'vista' on Windows
        available_themes = style.theme_names()
        if "clam" in available_themes:
            style.theme_use("clam")
        
        # Configure Fonts
        default_font = ("Segoe UI", 9)
        header_font = ("Segoe UI", 16, "bold")
        
        style.configure(".", font=default_font, background="#f5f5f5")
        style.configure("TFrame", background="#f5f5f5")
        style.configure("TLabel", background="#f5f5f5", foreground="#333333")
        style.configure("TButton", padding=5)
        style.configure("TEntry", padding=5)
        
        # Header Style
        style.configure("Header.TLabel", font=header_font, foreground="#1565c0")
        
        # LabelFrame Style
        style.configure("TLabelframe", background="#f5f5f5")
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground="#555555", background="#f5f5f5")
        
        # Accent Button (Connect)
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))
        
        # Treeview Style
        style.configure("Treeview", 
                        background="white",
                        foreground="black", 
                        rowheight=25,
                        fieldbackground="white",
                        font=("Segoe UI", 10))
        style.map("Treeview", background=[("selected", "#e3f2fd")], foreground=[("selected", "black")])
        
        # Main Window Background
        self.root.configure(bg="#f5f5f5")

    def handle_worker_event(self, event_type, data):
        # Schedule update in main thread
        self.root.after(0, lambda: self._process_event(event_type, data))

    def _process_event(self, event_type, data):
        if event_type == "connected":
            self.status_var.set(data)
            self.connect_btn.config(state=tk.NORMAL, text="Desconectar")
            self.delete_btn.config(state=tk.NORMAL)
        elif event_type == "disconnected":
            self.status_var.set(data)
            self.connect_btn.config(state=tk.NORMAL, text="Conectar")
            self.delete_btn.config(state=tk.DISABLED)
            self.tree.delete(*self.tree.get_children()) # Clear list
        elif event_type == "connection_error":
            self.status_var.set(f"Error: {data}")
            self.connect_btn.config(state=tk.NORMAL, text="Conectar")
            messagebox.showerror("Error", data)
        elif event_type == "file_list":
            self.update_file_list(data)
        elif event_type == "upload_progress":
            self.progress_var.set(data)
        elif event_type == "upload_finished":
            self.status_var.set(f"Subida completada: {data}")
            self.is_uploading = False
            if not self.upload_queue:
                self.progress_bar.pack_forget()
                messagebox.showinfo("Cola Finalizada", "Todos los archivos se han subido correctamente.")
            else:
                self.process_queue()
        elif event_type == "delete_finished":
            self.status_var.set(f"Archivo eliminado: {data}")
        elif event_type == "error":
            self.status_var.set(f"Error: {data}")
            self.is_uploading = False
            if self.upload_queue:
                if messagebox.askyesno("Error en cola", f"Ocurrió un error: {data}\n¿Desea continuar con el resto de la cola?"):
                    self.process_queue()
                else:
                    self.upload_queue.clear()
                    self.progress_bar.pack_forget()
            else:
                if "Delete failed" not in str(data):
                    messagebox.showerror("Error", data)

    def connect_ftp(self):
        if self.connect_btn.cget("text") == "Desconectar":
            self.status_var.set("Desconectando...")
            self.connect_btn.config(state=tk.DISABLED)
            self.worker.disconnect()
            return

        host = self.host_entry.get().strip()
        user = self.user_entry.get().strip()
        pwd = self.pass_entry.get().strip()

        if host.lower().startswith("ftp://"):
            host = host[6:]

        if not host or not user or not pwd:
            messagebox.showwarning("Error", "Por favor complete todos los campos")
            return

        # Debug logging
        try:
            with open("debug_log.txt", "a") as f:
                f.write(f"Attempting connect to: {host} with user: {user}\n")
        except:
            pass

        self.save_settings()
        self.connect_btn.config(state=tk.DISABLED)
        self.status_var.set("Conectando...")
        self.worker.connect_to_server(host, user, pwd)

    def update_file_list(self, files):
        self.tree.delete(*self.tree.get_children())
        self.select_all_var.set(False)
        for f in files:
            # Insert with unchecked state
            self.tree.insert("", "end", text=f"\u2610   {f}", values=(f, "unchecked")) 
        
        # Debug logging
        try:
            with open("debug_log.txt", "a") as f:
                f.write(f"Listed {len(files)} files\n")
        except:
            pass 

    def on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            current_text = self.tree.item(item_id, "text")
            filename = self.tree.item(item_id, "values")[0]
            current_state = self.tree.item(item_id, "values")[1]
            
            if current_state == "unchecked":
                new_text = f"\u2611   {filename}"
                new_state = "checked"
            else:
                new_text = f"\u2610   {filename}"
                new_state = "unchecked"
            
            self.tree.item(item_id, text=new_text, values=(filename, new_state))

    def toggle_select_all(self):
        state = self.select_all_var.get()
        for item_id in self.tree.get_children():
            filename = self.tree.item(item_id, "values")[0]
            if state:
                self.tree.item(item_id, text=f"\u2611   {filename}", values=(filename, "checked"))
            else:
                self.tree.item(item_id, text=f"\u2610   {filename}", values=(filename, "unchecked"))

    def open_file_dialog(self):
        if self.connect_btn.cget("text") != "Desconectar":
            messagebox.showwarning("No conectado", "Primero debes conectarte al servidor FTP.")
            return

        files = filedialog.askopenfilenames(title="Seleccionar archivos para subir")
        if files:
            self.add_to_queue(list(files))

    def delete_selected_files(self):
        files_to_delete = []
        for item_id in self.tree.get_children():
            if self.tree.item(item_id, "values")[1] == "checked":
                files_to_delete.append(self.tree.item(item_id, "values")[0])
        
        if not files_to_delete:
            messagebox.showinfo("Info", "No hay archivos seleccionados para eliminar")
            return

        if messagebox.askyesno("Confirmar", f"¿Estás seguro de eliminar {len(files_to_delete)} archivos?"):
            self.status_var.set("Eliminando archivos...")
            for f in files_to_delete:
                self.worker.delete_file(f)

    def on_drop(self, event):
        if self.connect_btn.cget("text") != "Desconectar":
            messagebox.showwarning("No conectado", "Primero debes conectarte al servidor FTP.")
            return
            
        files = self.root.tk.splitlist(event.data)
        valid_files = [f for f in files if os.path.isfile(f)]
        if valid_files:
            self.add_to_queue(valid_files)

    def add_to_queue(self, files):
        self.upload_queue.extend(files)
        self.status_var.set(f"Añadidos {len(files)} archivos a la cola. Total: {len(self.upload_queue)}")
        self.process_queue()

    def process_queue(self):
        if self.is_uploading or not self.upload_queue:
            return
        
        file_path = self.upload_queue.pop(0)
        self.is_uploading = True
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        self.progress_var.set(0)
        self.status_var.set(f"Subiendo {os.path.basename(file_path)}... (En cola: {len(self.upload_queue)})")
        self.worker.upload_file(file_path)

    def load_settings(self):
        # Disable interpolation to allow % characters in passwords
        config = configparser.ConfigParser(interpolation=None)
        if os.path.exists(self.settings_file):
            try:
                config.read(self.settings_file)
                
                # Debug logging
                with open("debug_log.txt", "a") as f:
                    f.write(f"Loading settings from {self.settings_file}\n")
                    f.write(f"Sections found: {config.sections()}\n")

                section = None
                if "General" in config:
                    section = "General"
                elif "Credentials" in config:
                    section = "Credentials"
                
                if section:
                    self.host_entry.insert(0, config[section].get("host", ""))
                    self.user_entry.insert(0, config[section].get("user", ""))
                    self.pass_entry.insert(0, config[section].get("password", ""))
                else:
                    with open("debug_log.txt", "a") as f:
                        f.write("No valid section found in settings.ini\n")

            except Exception as e:
                print(f"Error loading settings: {e}")
                try:
                    with open("debug_log.txt", "a") as f:
                        f.write(f"Error loading settings: {e}\n")
                except:
                    pass
        else:
            try:
                with open("debug_log.txt", "a") as f:
                    f.write(f"Settings file not found at {self.settings_file}\n")
            except:
                pass

    def save_settings(self):
        # Disable interpolation here too just in case
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
            print(f"Error saving settings: {e}")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = FTPClientApp(root)
    root.mainloop()
