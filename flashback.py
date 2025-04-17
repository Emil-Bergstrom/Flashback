import json
from pathlib import Path
from datetime import datetime, timedelta
from tkinter import filedialog, Menu
from PIL import Image, ImageTk
import cv2
import subprocess
import platform
import customtkinter as ctk

# Constants
THUMBNAIL_WIDTH = 150
THUMBNAIL_HEIGHT = 84
COLUMN_WIDTH = 210
DEBOUNCE_DELAY = 200
WINDOW_SIZE = "750x600"

class FlashbackApp:
    def __init__(self):
        self.config_file = Path("video_paths.json")
        self.thumbnail_cache = {}
        self.current_width = 0
        self.resize_after_id = None
        self.folder_management_frame = None
        self.label_frame = None
        self.show_this_week = False
        
        self.setup_ui()
        
    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        self.app = ctk.CTk()
        self.app.title("Flashback Videos")
        self.app.geometry(WINDOW_SIZE)
        
        # Set the window icon/favicon
        try:
            favicon_path = Path("favicon.ico")
            if favicon_path.exists():
                self.app.iconbitmap(str(favicon_path))
            else:
                print("favicon.ico not found")
        except Exception as e:
            print(f"Error setting window icon: {e}")
        
        # Top frame for controls
        control_frame = ctk.CTkFrame(self.app, fg_color="transparent")
        control_frame.pack(fill="x", padx=20, pady=(10,0))
        
        # Title label
        self.title_label = ctk.CTkLabel(
            control_frame, 
            text="This Day in History", 
            fg_color="transparent"
        )
        self.title_label.pack(side="left")
        
        # View toggle button
        self.view_toggle = ctk.CTkButton(
            control_frame,
            text="Switch to This Week",
            command=self.toggle_view,
            width=120
        )
        self.view_toggle.pack(side="right")
        
        # Create a container frame for the scrollable area
        self.container_frame = ctk.CTkFrame(self.app)
        self.container_frame.pack(fill="both", expand=True, padx=20, pady=(10,20))
        
        # Video frame (scrollable)
        self.video_frame = ctk.CTkScrollableFrame(
            self.container_frame,
            orientation="vertical"
        )
        self.video_frame.pack(fill="both", expand=True)
        
        # Grid configuration for the video frame
        self.video_grid = ctk.CTkFrame(self.video_frame, fg_color="transparent")
        self.video_grid.pack(fill="both", expand=True)
        
        # Change folders button
        change_folder_btn = ctk.CTkButton(
            self.app, 
            text="Change Folders", 
            command=self.toggle_folder_management
        )
        change_folder_btn.pack(pady=(0,20))
        
        # Context menu for videos
        self.context_menu = Menu(self.app, tearoff=0)
        self.context_menu.add_command(label="Show in Folder", command=self.show_in_folder)
        
        self.create_folder_management_frame()
        self.app.bind("<Configure>", self.on_resize)
        self.clean_missing_folders()  # Clean missing folders on startup
        self.update_video_display()

    def clean_missing_folders(self):
        paths = self.load_paths()
        valid_paths = [str(path) for path in paths if Path(path).exists()]
        
        if len(valid_paths) != len(paths):
            self.save_paths(valid_paths)
            return True
        return False

    def show_in_folder(self):
        if hasattr(self, 'selected_video'):
            video_path = Path(self.selected_video)
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{video_path}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', '-R', str(video_path)])
            else:
                subprocess.Popen(['xdg-open', str(video_path.parent)])

    def create_video_button(self, video_file, photo, text, row, col):
        btn = ctk.CTkButton(
            self.video_grid,
            image=photo,
            text=text,
            compound="top",
            command=lambda f=video_file: self.open_video(f),
            width=THUMBNAIL_WIDTH,
            height=THUMBNAIL_HEIGHT
        )
        btn.photo = photo
        btn.grid(row=row, column=col, padx=10, pady=10, ipady=10, sticky="nsew")
        
        # Bind right-click to show context menu
        btn.bind('<Button-3>', lambda e, f=video_file: self.show_context_menu(e, f))
        
        return btn

    def show_context_menu(self, event, video_file):
        self.selected_video = video_file
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def toggle_view(self):
        self.show_this_week = not self.show_this_week
        
        # Update button text
        new_text = "Switch to Today" if self.show_this_week else "Switch to This Week"
        self.view_toggle.configure(text=new_text)
        
        # Update title label text
        new_title = "This Week in History" if self.show_this_week else "This Day in History"
        self.title_label.configure(text=new_title)
        
        # Show loading state
        for widget in self.video_grid.winfo_children():
            widget.destroy()
        loading_label = ctk.CTkLabel(self.video_grid, text="Loading videos...", text_color="gray")
        loading_label.pack(pady=20)
        
        # Schedule the update after a short delay to allow UI to refresh
        self.app.after(100, lambda: self.finish_view_toggle(loading_label))
    
    def finish_view_toggle(self, loading_label):
        # Remove loading label
        loading_label.destroy()
        # Update the display
        self.update_video_display()

    def get_flashback_videos(self):
        today = datetime.now()
        matching_videos = []
        
        for folder in self.load_paths():
            try:
                folder_path = Path(folder)
                if not folder_path.exists():
                    continue
                    
                for video_file in folder_path.rglob("*.mp4"):
                    creation_time = datetime.fromtimestamp(video_file.stat().st_ctime)
                    
                    if self.show_this_week:
                        # For this week view: show videos from past years for current week
                        current_week = today.isocalendar()[1]
                        video_week = creation_time.isocalendar()[1]
                        
                        if (video_week == current_week and 
                            creation_time.year < today.year):
                            years_ago = today.year - creation_time.year
                            if thumbnail := self.get_thumbnail(video_file):
                                matching_videos.append((years_ago, video_file, thumbnail))
                    else:
                        # For this day view: show videos from same day in past years
                        if (creation_time.month == today.month and 
                            creation_time.day == today.day and 
                            (years_ago := today.year - creation_time.year) > 0):
                            
                            if thumbnail := self.get_thumbnail(video_file):
                                matching_videos.append((years_ago, video_file, thumbnail))
                                
            except Exception as e:
                print(f"Error processing folder {folder}: {e}")
                
        return sorted(matching_videos, key=lambda x: x[0])

    def calculate_and_display_videos(self):
        try:
            self.container_frame.update_idletasks()
            current_width = self.container_frame.winfo_width()
            maxcol = max(1, current_width // COLUMN_WIDTH)
            
            # Clear existing videos
            for widget in self.video_grid.winfo_children():
                widget.destroy()
            
            # Configure grid columns to have fixed width
            for i in range(maxcol):
                self.video_grid.grid_columnconfigure(i, minsize=COLUMN_WIDTH, weight=0)
            
            flashback_videos = self.get_flashback_videos()
            if not flashback_videos:
                message = ("No videos found from this week in previous years." 
                          if self.show_this_week 
                          else "No videos found from this day in previous years.")
                no_videos_label = ctk.CTkLabel(
                    self.video_grid,
                    text=message,
                    text_color="gray"
                )
                no_videos_label.pack(pady=20)
                return
            
            for idx, (years_ago, video_file, thumbnail) in enumerate(flashback_videos):
                img = thumbnail.resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
                photo = ImageTk.PhotoImage(img)
                
                row, col = divmod(idx, maxcol)
                self.create_video_button(
                    video_file,
                    photo,
                    f"{years_ago} year(s) ago",
                    row,
                    col
                )
                
            self.current_width = current_width
            
        except Exception as e:
            print(f"Error displaying videos: {e}")

    def update_video_display(self):
        self.video_frame.after(100, self.calculate_and_display_videos)

    def remove_folder(self, path):
        paths = self.load_paths()
        if path in paths:
            paths.remove(path)
            self.save_paths(paths)
            self.update_folder_list()
            self.update_video_display()

    def update_folder_list(self):
        for widget in self.folder_management_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and widget is not self.label_frame:
                widget.destroy()
        
        for path in self.load_paths():
            folder_frame = ctk.CTkFrame(self.folder_management_frame, fg_color="transparent")
            folder_frame.pack(fill="x", pady=5, padx=10)
            
            label = ctk.CTkLabel(folder_frame, text=str(path), anchor="w")
            label.pack(side="left", fill="x", expand=True, padx=10)
            
            delete_button = ctk.CTkButton(
                folder_frame,
                text="Remove",
                command=lambda p=path: self.remove_folder(p)
            )
            delete_button.pack(side="right")

    def create_folder_management_frame(self):
        self.folder_management_frame = ctk.CTkFrame(self.app)
        self.label_frame = ctk.CTkFrame(self.folder_management_frame)
        self.label_frame.pack(fill="x", pady=10, padx=10)
        
        label = ctk.CTkLabel(self.label_frame, text="Manage Folders")
        label.pack(side="left", padx=10, pady=5)
        
        add_button = ctk.CTkButton(
            self.folder_management_frame,
            text="Add Folder",
            command=self.add_folder
        )
        add_button.pack(side="bottom", padx=5, pady=(0,10))
        self.update_folder_list()

    def add_folder(self):
        if new_path := filedialog.askdirectory():
            paths = self.load_paths()
            if new_path not in paths:
                paths.append(new_path)
                self.save_paths(paths)
                self.update_folder_list()
                self.update_video_display()

    def toggle_folder_management(self):
        if self.folder_management_frame.winfo_ismapped():
            self.folder_management_frame.pack_forget()
        else:
            self.folder_management_frame.pack(fill="both", expand=True, padx=20, pady=(0,20))
            self.update_folder_list()

    def on_resize(self, event):
        if self.resize_after_id:
            self.video_frame.after_cancel(self.resize_after_id)
        self.resize_after_id = self.video_frame.after(
            DEBOUNCE_DELAY,
            lambda: self.update_video_display() if self.container_frame.winfo_width() != self.current_width else None
        )

    def load_paths(self):
        try:
            if self.config_file.exists():
                return json.loads(self.config_file.read_text())
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading paths: {e}")
        return []

    def save_paths(self, paths):
        try:
            self.config_file.write_text(json.dumps(paths))
        except IOError as e:
            print(f"Error saving paths: {e}")

    @staticmethod
    def open_video(file_path):
        try:
            if platform.system() == "Windows":
                subprocess.Popen(['start', '', str(file_path)], shell=True)
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', str(file_path)])
            else:
                subprocess.Popen(['xdg-open', str(file_path)])
        except subprocess.SubprocessError as e:
            print(f"Error opening video: {e}")

    def get_thumbnail(self, video_path):
        video_path_str = str(video_path)
        if video_path_str in self.thumbnail_cache:
            return self.thumbnail_cache[video_path_str]
            
        try:
            vidcap = cv2.VideoCapture(video_path_str)
            success, image = vidcap.read()
            vidcap.release()
            
            if success:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(image)
                self.thumbnail_cache[video_path_str] = img
                return img
        except Exception as e:
            print(f"Error generating thumbnail for {video_path}: {e}")
        return None

    def run(self):
        self.app.mainloop()

if __name__ == "__main__":
    app = FlashbackApp()
    app.run()
