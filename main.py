import os
import threading
import time

import wx
import winsound

from webdav3.client import Client

import settings

APP_TITLE = "SA Access Archive - by Raeez Kuhn, Eezo the Blind DJ"

SOUND_LAUNCH = (880, 150)
SOUND_FOLDER = (660, 80)
SOUND_DONE = (990, 200)
SOUND_ERROR = (220, 300)


class DownloadThread(threading.Thread):
    """Downloads a single file in the background so the app stays responsive."""

    def __init__(self, client, remote_path, local_path, on_progress,
                 on_finished, on_error):
        super().__init__(daemon=True)
        self.client = client
        self.remote_path = remote_path
        self.local_path = local_path
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_error = on_error

    def run(self):
        try:
            self.on_progress("Starting download: "
                             + os.path.basename(self.local_path))
            self.client.download_sync(
                remote_path=self.remote_path,
                local_path=self.local_path
            )
            self.on_finished(self.local_path)
        except Exception as error:
            self.on_error(str(error))


class MainWindow(wx.Frame):

    def __init__(self):
        super().__init__(parent=None, title=APP_TITLE, size=(900, 600))

        self.config = settings.load_settings()
        self.current_folder = settings.get(self.config, "start_folder")

        if not os.path.isdir(self.current_folder):
            self.current_folder = os.path.expanduser("~")

        self.remote_mode = False
        self.remote_client = None
        self.remote_path = "/"
        self.download_in_progress = False
        self.search_active = False

        self.build_menu_bar()
        self.build_body()

        self.Centre()
        self.Show()

        self.focus_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_focus_timer, self.focus_timer)
        self.focus_timer.Start(200, oneShot=True)

        self.load_local_folder(self.current_folder)
        self.play_sound(SOUND_LAUNCH)

        # Show the welcome screen on first run only.
        if settings.get(self.config, "first_run_complete") != "yes":
            self.show_welcome()

    def show_welcome(self):
        dialog = WelcomeDialog(self)
        dialog.ShowModal()
        dialog.Destroy()
        settings.set_value(self.config, "first_run_complete", "yes")
        self.item_list.SetFocus()

    def play_sound(self, tone):
        if settings.get(self.config, "sounds_enabled") != "yes":
            return
        try:
            frequency, duration = tone
            winsound.Beep(int(frequency), int(duration))
        except Exception:
            pass

    def on_focus_timer(self, event):
        self.item_list.SetFocus()
        if self.item_list.GetItemCount() > 0:
            self.item_list.Focus(0)
            self.item_list.Select(0)

    def build_menu_bar(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        file_menu.Append(4001, "Refresh\tF5")
        file_menu.Append(4003, "Download Selected\tCtrl+D")
        file_menu.Append(4004, "Open Download Folder")
        file_menu.AppendSeparator()
        file_menu.Append(4002, "Quit\tCtrl+Q")
        menu_bar.Append(file_menu, "File")

        nav_menu = wx.Menu()
        nav_menu.Append(3001, "Up One Level\tBackspace")
        nav_menu.Append(3002, "Home\tHome")
        nav_menu.Append(3003, "End\tEnd")
        nav_menu.AppendSeparator()
        nav_menu.Append(3005, "Show Info\tI")
        nav_menu.Append(3004, "Search\tCtrl+F")
        menu_bar.Append(nav_menu, "Navigate")

        settings_menu = wx.Menu()
        settings_menu.Append(5006, "Server Settings")
        settings_menu.Append(5007, "Connect to Server")
        settings_menu.Append(5008, "Disconnect")
        settings_menu.AppendSeparator()
        settings_menu.Append(5002, "Set Download Folder")
        settings_menu.Append(5003, "Set Local Start Folder")
        settings_menu.Append(5005, "Toggle Sounds")
        settings_menu.Append(5010, "Show Welcome Screen Again")
        settings_menu.Append(5004, "Reset All Settings")
        menu_bar.Append(settings_menu, "Settings")

        help_menu = wx.Menu()
        help_menu.Append(6001, "Keyboard Shortcuts\tF1")
        menu_bar.Append(help_menu, "Help")

        about_menu = wx.Menu()
        about_menu.Append(7001, "About SA Access Archive")
        menu_bar.Append(about_menu, "About")

        self.SetMenuBar(menu_bar)

        self.Bind(wx.EVT_MENU, self.on_refresh, id=4001)
        self.Bind(wx.EVT_MENU, self.on_download_selected, id=4003)
        self.Bind(wx.EVT_MENU, self.on_open_download_folder, id=4004)
        self.Bind(wx.EVT_MENU, self.on_quit, id=4002)
        self.Bind(wx.EVT_MENU, self.on_up_level, id=3001)
        self.Bind(wx.EVT_MENU, self.on_home, id=3002)
        self.Bind(wx.EVT_MENU, self.on_end, id=3003)
        self.Bind(wx.EVT_MENU, self.on_show_info, id=3005)
        self.Bind(wx.EVT_MENU, self.on_search, id=3004)
        self.Bind(wx.EVT_MENU, self.on_server_settings, id=5006)
        self.Bind(wx.EVT_MENU, self.on_connect, id=5007)
        self.Bind(wx.EVT_MENU, self.on_disconnect, id=5008)
        self.Bind(wx.EVT_MENU, self.on_set_download_folder, id=5002)
        self.Bind(wx.EVT_MENU, self.on_set_start_folder, id=5003)
        self.Bind(wx.EVT_MENU, self.on_toggle_sounds, id=5005)
        self.Bind(wx.EVT_MENU, self.on_show_welcome_again, id=5010)
        self.Bind(wx.EVT_MENU, self.on_reset_settings, id=5004)
        self.Bind(wx.EVT_MENU, self.on_help, id=6001)
        self.Bind(wx.EVT_MENU, self.on_about, id=7001)

    def build_body(self):
        panel = wx.Panel(self)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(panel, label="Loading...")
        sizer.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 10)

        self.item_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL
        )
        self.item_list.InsertColumn(0, "Name", width=450)
        self.item_list.InsertColumn(1, "Type", width=150)
        self.item_list.InsertColumn(2, "Size", width=150)

        sizer.Add(self.item_list, 1, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(sizer)

        self.panel = panel
        self.item_list.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.item_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_item_activated)

    def load_local_folder(self, folder):
        self.search_active = False
        self.remote_mode = False
        self.current_folder = folder
        self.item_list.DeleteAllItems()

        try:
            entries = sorted(os.listdir(folder))
        except OSError as error:
            self.status_label.SetLabel("Could not read folder: " + str(error))
            self.play_sound(SOUND_ERROR)
            return

        folders = []
        files = []
        for entry in entries:
            full_path = os.path.join(folder, entry)
            if os.path.isdir(full_path):
                folders.append(entry)
            else:
                files.append(entry)

        for name in folders:
            self.add_row(name, "Folder", "-")

        for name in files:
            full_path = os.path.join(folder, name)
            try:
                size_bytes = os.path.getsize(full_path)
                size_text = self.format_size(size_bytes)
            except OSError:
                size_text = "?"
            self.add_row(name, "File", size_text)

        total = len(folders) + len(files)
        self.status_label.SetLabel(
            "Local: " + folder + "  (" + str(total) + " items)"
        )
        self.Layout()

    def load_remote_folder(self, path):
        self.search_active = False
        self.remote_mode = True
        self.remote_path = path
        self.item_list.DeleteAllItems()

        if self.remote_client is None:
            self.status_label.SetLabel("Not connected to a server.")
            self.play_sound(SOUND_ERROR)
            return

        try:
            entries = self.remote_client.list(path)
        except Exception as error:
            self.status_label.SetLabel(
                "Could not read remote folder: " + str(error)
            )
            self.play_sound(SOUND_ERROR)
            return

        folders = []
        files = []

        for entry in entries:
            clean = entry.rstrip("/")
            if clean == "" or clean == ".":
                continue
            if entry.endswith("/"):
                folders.append(clean)
            else:
                files.append(clean)

        folders.sort(key=str.lower)
        files.sort(key=str.lower)

        for name in folders:
            self.add_row(name, "Remote Folder", "-")

        for name in files:
            self.add_row(name, "Remote File", "?")

        total = len(folders) + len(files)
        self.status_label.SetLabel(
            "Remote: " + path + "  (" + str(total) + " items)"
        )
        self.Layout()

    def add_row(self, name, item_type, size):
        index = self.item_list.InsertItem(
            self.item_list.GetItemCount(), name
        )
        self.item_list.SetItem(index, 1, item_type)
        self.item_list.SetItem(index, 2, size)

    def format_size(self, size_bytes):
        if size_bytes < 1024:
            return str(size_bytes) + " B"
        if size_bytes < 1024 * 1024:
            return str(size_bytes // 1024) + " KB"
        if size_bytes < 1024 * 1024 * 1024:
            return str(size_bytes // (1024 * 1024)) + " MB"
        return str(size_bytes // (1024 * 1024 * 1024)) + " GB"

    def format_time(self, timestamp):
        try:
            return time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(timestamp)
            )
        except (ValueError, OSError):
            return "(unknown)"

    def get_selected_name(self):
        index = self.item_list.GetFirstSelected()
        if index == -1:
            return None
        return self.item_list.GetItemText(index, 0)

    def get_selected_type(self):
        index = self.item_list.GetFirstSelected()
        if index == -1:
            return None
        return self.item_list.GetItemText(index, 1)

    def on_key_down(self, event):
        key = event.GetKeyCode()

        if key == wx.WXK_ESCAPE:
            if self.search_active:
                self.clear_search()
            else:
                self.Close()
        elif key == wx.WXK_BACK:
            if self.search_active:
                self.clear_search()
            else:
                self.on_up_level(None)
        elif key == wx.WXK_HOME:
            self.on_home(None)
        elif key == wx.WXK_END:
            self.on_end(None)
        elif key == wx.WXK_RETURN or key == wx.WXK_NUMPAD_ENTER:
            self.open_selected()
        elif key == ord("I") or key == ord("i"):
            self.on_show_info(None)
        else:
            char = event.GetUnicodeKey()
            if char != wx.WXK_NONE and chr(char).isalnum():
                self.jump_to_letter(chr(char))
                event.Skip()
            else:
                event.Skip()

    def jump_to_letter(self, letter):
        count = self.item_list.GetItemCount()
        if count == 0:
            return

        current = self.item_list.GetFirstSelected()
        if current == -1:
            current = 0
            start = 0
        else:
            start = current + 1

        lower = letter.lower()
        for offset in range(count):
            index = (start + offset) % count
            name = self.item_list.GetItemText(index, 0)
            if name and name[0].lower() == lower:
                self.item_list.Focus(index)
                self.item_list.Select(index)
                return

    def on_item_activated(self, event):
        self.open_selected()

    def open_selected(self):
        name = self.get_selected_name()
        item_type = self.get_selected_type()

        if name is None or item_type is None:
            return

        if self.remote_mode:
            remote_full = self.remote_path.rstrip("/") + "/" + name
            if item_type == "Remote Folder":
                self.load_remote_folder(remote_full)
                self.play_sound(SOUND_FOLDER)
                self.item_list.SetFocus()
                if self.item_list.GetItemCount() > 0:
                    self.item_list.Focus(0)
                    self.item_list.Select(0)
            else:
                self.download_remote_file(name)
        else:
            local_full = os.path.join(self.current_folder, name)
            if item_type == "Folder":
                self.load_local_folder(local_full)
                self.play_sound(SOUND_FOLDER)
                self.item_list.SetFocus()
                if self.item_list.GetItemCount() > 0:
                    self.item_list.Focus(0)
                    self.item_list.Select(0)
            else:
                self.status_label.SetLabel(
                    "Local file: " + name
                    + "  (already on your computer)"
                )
                self.Layout()

    def download_remote_file(self, name):
        if self.download_in_progress:
            wx.MessageBox(
                "A download is already in progress.\n\n"
                "Wait for it to finish before starting another.",
                "Please wait",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        if self.remote_client is None:
            wx.MessageBox(
                "Not connected to a server.",
                "Cannot download",
                wx.OK | wx.ICON_ERROR, self
            )
            return

        download_folder = settings.get(self.config, "download_folder")
        if not os.path.isdir(download_folder):
            wx.MessageBox(
                "The download folder does not exist:\n"
                + download_folder,
                "Cannot download",
                wx.OK | wx.ICON_ERROR, self
            )
            return

        local_path = os.path.join(download_folder, name)
        remote_path = self.remote_path.rstrip("/") + "/" + name

        self.download_in_progress = True
        self.status_label.SetLabel("Downloading: " + name)
        self.Layout()

        thread = DownloadThread(
            client=self.remote_client,
            remote_path=remote_path,
            local_path=local_path,
            on_progress=self.on_download_progress,
            on_finished=self.on_download_finished,
            on_error=self.on_download_error,
        )
        thread.start()

    def on_download_progress(self, message):
        wx.CallAfter(self.update_status, message)

    def on_download_finished(self, local_path):
        wx.CallAfter(self.finish_download, local_path)

    def on_download_error(self, message):
        wx.CallAfter(self.fail_download, message)

    def update_status(self, message):
        self.status_label.SetLabel(message)
        self.Layout()

    def finish_download(self, local_path):
        self.download_in_progress = False
        self.status_label.SetLabel(
            "Download complete: " + local_path
        )
        self.play_sound(SOUND_DONE)
        self.Layout()
        wx.MessageBox(
            "Download complete:\n\n" + local_path,
            "Download finished",
            wx.OK | wx.ICON_INFORMATION, self
        )

    def fail_download(self, message):
        self.download_in_progress = False
        self.status_label.SetLabel("Download failed: " + message)
        self.play_sound(SOUND_ERROR)
        self.Layout()
        wx.MessageBox(
            "Download failed:\n\n" + message,
            "Download failed",
            wx.OK | wx.ICON_ERROR, self
        )

    def on_download_selected(self, event):
        if self.remote_mode:
            name = self.get_selected_name()
            item_type = self.get_selected_type()
            if name and item_type == "Remote File":
                self.download_remote_file(name)
            else:
                wx.MessageBox(
                    "Select a remote file first.",
                    "Nothing to download",
                    wx.OK | wx.ICON_INFORMATION, self
                )
        else:
            wx.MessageBox(
                "This option downloads files from a remote server.\n\n"
                "Connect to a server first.",
                "Not in remote mode",
                wx.OK | wx.ICON_INFORMATION, self
            )

    def on_open_download_folder(self, event):
        folder = settings.get(self.config, "download_folder")
        if os.path.isdir(folder):
            try:
                os.startfile(folder)
            except OSError as error:
                wx.MessageBox(
                    "Could not open folder:\n" + str(error),
                    "Error",
                    wx.OK | wx.ICON_ERROR, self
                )
        else:
            wx.MessageBox(
                "The download folder does not exist:\n" + folder,
                "Not found",
                wx.OK | wx.ICON_ERROR, self
            )

    def on_search(self, event):
        if self.search_active:
            self.clear_search()
            return

        dialog = SearchDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            term = dialog.get_term()
            if term:
                self.apply_search(term)
        dialog.Destroy()

    def apply_search(self, term):
        self.search_active = True

        lower = term.lower()
        count_before = self.item_list.GetItemCount()
        matches = []

        for i in range(count_before):
            name = self.item_list.GetItemText(i, 0)
            item_type = self.item_list.GetItemText(i, 1)
            size = self.item_list.GetItemText(i, 2)
            if lower in name.lower():
                matches.append((name, item_type, size))

        self.item_list.DeleteAllItems()

        for name, item_type, size in matches:
            self.add_row(name, item_type, size)

        self.status_label.SetLabel(
            "Search results for '" + term + "': "
            + str(len(matches)) + " of " + str(count_before)
            + " items  (Backspace or Escape to clear)"
        )
        self.Layout()

        self.item_list.SetFocus()
        if self.item_list.GetItemCount() > 0:
            self.item_list.Focus(0)
            self.item_list.Select(0)

    def clear_search(self):
        self.search_active = False
        if self.remote_mode:
            self.load_remote_folder(self.remote_path)
        else:
            self.load_local_folder(self.current_folder)
        self.play_sound(SOUND_FOLDER)
        self.item_list.SetFocus()
        if self.item_list.GetItemCount() > 0:
            self.item_list.Focus(0)
            self.item_list.Select(0)

    def on_up_level(self, event):
        if self.remote_mode:
            if self.remote_path in ("/", ""):
                self.status_label.SetLabel(
                    "Already at the remote top level."
                )
                self.Layout()
                return
            parent = os.path.dirname(self.remote_path.rstrip("/"))
            if parent == "":
                parent = "/"
            self.load_remote_folder(parent)
            self.play_sound(SOUND_FOLDER)
            self.item_list.SetFocus()
            if self.item_list.GetItemCount() > 0:
                self.item_list.Focus(0)
                self.item_list.Select(0)
        else:
            parent = os.path.dirname(self.current_folder)
            if parent and parent != self.current_folder:
                self.load_local_folder(parent)
                self.play_sound(SOUND_FOLDER)
                self.item_list.SetFocus()
                if self.item_list.GetItemCount() > 0:
                    self.item_list.Focus(0)
                    self.item_list.Select(0)
            else:
                self.status_label.SetLabel("Already at the top level.")
                self.Layout()

    def on_refresh(self, event):
        if self.remote_mode:
            self.load_remote_folder(self.remote_path)
        else:
            self.load_local_folder(self.current_folder)
        self.play_sound(SOUND_FOLDER)
        self.item_list.SetFocus()
        if self.item_list.GetItemCount() > 0:
            self.item_list.Focus(0)
            self.item_list.Select(0)

    def on_home(self, event):
        if self.item_list.GetItemCount() > 0:
            self.item_list.Focus(0)
            self.item_list.Select(0)
        self.item_list.SetFocus()

    def on_end(self, event):
        count = self.item_list.GetItemCount()
        if count > 0:
            last = count - 1
            self.item_list.Focus(last)
            self.item_list.Select(last)
        self.item_list.SetFocus()

    def on_show_info(self, event):
        name = self.get_selected_name()
        item_type = self.get_selected_type()

        if name is None or item_type is None:
            wx.MessageBox(
                "Nothing is selected.",
                "Item Info",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        if self.remote_mode:
            remote_full = self.remote_path.rstrip("/") + "/" + name
            download_folder = settings.get(self.config, "download_folder")
            local_target = os.path.join(download_folder, name)
            info_lines = [
                "Name: " + name,
                "Type: " + item_type,
                "Remote path: " + remote_full,
                "Mode: Remote (connected to server)",
                "Will download to: " + local_target,
            ]
            text = "\n".join(info_lines)
            wx.MessageBox(
                text, "Item Info",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        full_path = os.path.join(self.current_folder, name)

        info_lines = []
        info_lines.append("Name: " + name)
        info_lines.append("Type: " + item_type)
        info_lines.append("Full path: " + full_path)

        try:
            stat = os.stat(full_path)
            size_bytes = stat.st_size
            info_lines.append(
                "Size: " + self.format_size(size_bytes)
                + "  (" + str(size_bytes) + " bytes)"
            )
            info_lines.append("Created: " + self.format_time(stat.st_ctime))
            info_lines.append("Modified: " + self.format_time(stat.st_mtime))
            info_lines.append("Accessed: " + self.format_time(stat.st_atime))

            if os.path.isfile(full_path):
                extension = os.path.splitext(name)[1]
                if extension:
                    info_lines.append("Extension: " + extension)
                else:
                    info_lines.append("Extension: (none)")
        except OSError as error:
            info_lines.append("Could not read details: " + str(error))

        try:
            writable = os.access(full_path, os.W_OK)
            info_lines.append("Read only: " + ("No" if writable else "Yes"))
        except OSError:
            pass

        text = "\n".join(info_lines)

        wx.MessageBox(
            text, "Item Info",
            wx.OK | wx.ICON_INFORMATION, self
        )

    def on_server_settings(self, event):
        address = settings.get(self.config, "server_address")
        username = settings.get(self.config, "server_username")
        password = settings.get(self.config, "server_password")

        dialog = ServerSettingsDialog(self, address, username, password)
        if dialog.ShowModal() == wx.ID_OK:
            settings.set_value(self.config, "server_address",
                               dialog.get_address())
            settings.set_value(self.config, "server_username",
                               dialog.get_username())
            settings.set_value(self.config, "server_password",
                               dialog.get_password())
            wx.MessageBox(
                "Server settings saved.",
                "Saved",
                wx.OK | wx.ICON_INFORMATION, self
            )
        dialog.Destroy()

    def on_connect(self, event):
        address = settings.get(self.config, "server_address")
        username = settings.get(self.config, "server_username")
        password = settings.get(self.config, "server_password")

        if not address:
            wx.MessageBox(
                "No server address is set.\n\n"
                "Use Settings, Server Settings to enter the address,\n"
                "username, and password first.",
                "Not configured",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        try:
            options = {
                "webdav_hostname": address,
                "webdav_login": username,
                "webdav_password": password,
            }
            self.remote_client = Client(options)
            self.remote_client.list("/")
            self.load_remote_folder("/")
            self.play_sound(SOUND_DONE)
            self.item_list.SetFocus()
            if self.item_list.GetItemCount() > 0:
                self.item_list.Focus(0)
                self.item_list.Select(0)
        except Exception as error:
            self.remote_client = None
            self.status_label.SetLabel("Connect failed: " + str(error))
            self.play_sound(SOUND_ERROR)
            wx.MessageBox(
                "Could not connect to the server.\n\n"
                "Error: " + str(error),
                "Connection failed",
                wx.OK | wx.ICON_ERROR, self
            )

    def on_disconnect(self, event):
        self.remote_client = None
        self.remote_mode = False
        self.remote_path = "/"
        self.search_active = False
        self.load_local_folder(self.current_folder)
        self.status_label.SetLabel(
            "Local: " + self.current_folder
            + "  (disconnected from server)"
        )
        self.Layout()

    def on_set_start_folder(self, event):
        dialog = wx.DirDialog(
            self, "Choose the folder to open on startup",
            defaultPath=self.current_folder,
            style=wx.DD_DEFAULT_STYLE
        )
        if dialog.ShowModal() == wx.ID_OK:
            chosen = dialog.GetPath()
            settings.set_value(self.config, "start_folder", chosen)
            self.load_local_folder(chosen)
            self.item_list.SetFocus()
            if self.item_list.GetItemCount() > 0:
                self.item_list.Focus(0)
                self.item_list.Select(0)
        dialog.Destroy()

    def on_set_download_folder(self, event):
        current = settings.get(self.config, "download_folder")
        dialog = wx.DirDialog(
            self, "Choose where downloads will be saved",
            defaultPath=current,
            style=wx.DD_DEFAULT_STYLE
        )
        if dialog.ShowModal() == wx.ID_OK:
            chosen = dialog.GetPath()
            settings.set_value(self.config, "download_folder", chosen)
            wx.MessageBox(
                "Download folder set to:\n" + chosen,
                "Saved",
                wx.OK | wx.ICON_INFORMATION, self
            )
        dialog.Destroy()

    def on_toggle_sounds(self, event):
        current = settings.get(self.config, "sounds_enabled")
        new_value = "no" if current == "yes" else "yes"
        settings.set_value(self.config, "sounds_enabled", new_value)

        if new_value == "yes":
            self.play_sound(SOUND_LAUNCH)
            wx.MessageBox(
                "Sounds are now ON.",
                "Sounds",
                wx.OK | wx.ICON_INFORMATION, self
            )
        else:
            wx.MessageBox(
                "Sounds are now OFF.",
                "Sounds",
                wx.OK | wx.ICON_INFORMATION, self
            )

    def on_show_welcome_again(self, event):
        settings.set_value(self.config, "first_run_complete", "no")
        self.show_welcome()

    def on_reset_settings(self, event):
        answer = wx.MessageBox(
            "Reset all settings to their defaults?",
            "Confirm reset",
            wx.YES_NO | wx.ICON_QUESTION, self
        )
        if answer == wx.YES:
            for key, value in settings.DEFAULTS.items():
                settings.set_value(self.config, key, value)
            self.load_local_folder(
                settings.get(self.config, "start_folder")
            )
            self.item_list.SetFocus()
            if self.item_list.GetItemCount() > 0:
                self.item_list.Focus(0)
                self.item_list.Select(0)

    def on_quit(self, event):
        self.Close()

    def on_placeholder(self, event):
        wx.MessageBox(
            "This feature will be added in a later build.",
            "Not yet available",
            wx.OK | wx.ICON_INFORMATION,
            self
        )

    def on_help(self, event):
        wx.MessageBox(
            "Keyboard shortcuts:\n\n"
            "Up and Down - move through the list\n"
            "Enter - open a folder, or download a remote file\n"
            "Backspace - go up one level\n"
            "Home - first item\n"
            "End - last item\n"
            "I - show info for the selected item\n"
            "Letter or number - jump to the next item starting with it\n"
            "Ctrl+F - search the current folder\n"
            "Ctrl+D - download the selected remote file\n"
            "Escape - clear search, or close the application\n"
            "F5 - refresh\n"
            "Ctrl+Q - quit\n"
            "F1 - this help screen\n\n"
            "Menu shortcuts:\n"
            "Alt+F - File\n"
            "Alt+N - Navigate\n"
            "Alt+S - Settings\n"
            "Alt+H - Help\n"
            "Alt+A - About",
            "Keyboard Shortcuts",
            wx.OK | wx.ICON_INFORMATION,
            self
        )

    def on_about(self, event):
        wx.MessageBox(
            "SA Access Archive\n"
            "Version 1.2\n\n"
            "Developed by Raeez Kuhn, Eezo the Blind DJ\n"
            "Based in South Africa\n\n"
            "A South African accessible archive for blind and\n"
            "visually impaired users.",
            "About SA Access Archive",
            wx.OK | wx.ICON_INFORMATION,
            self
        )


class WelcomeDialog(wx.Dialog):
    """The first-run welcome message."""

    def __init__(self, parent):
        super().__init__(
            parent,
            title="Welcome to SA Access Archive",
            size=(700, 500)
        )

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        welcome_text = (
            "Welcome to SA Access Archive\n"
            "Version 1.2\n\n"
            "An accessible archive client for blind and visually\n"
            "impaired users in South Africa.\n\n"
            "Developed by Raeez Kuhn, also known as Eezo the\n"
            "Blind DJ.\n\n"
            "What you can do here:\n\n"
            "1. Browse folders on your own computer. Use the Up and\n"
            "Down arrows to move through the list, Enter to open a\n"
            "folder, and Backspace to go up a level.\n\n"
            "2. Connect to a remote archive over the internet. Press\n"
            "Alt+S to open the Settings menu, choose Server\n"
            "Settings, enter your server address and login, then\n"
            "choose Connect to Server.\n\n"
            "3. Search the current folder with Ctrl+F.\n\n"
            "4. Press F1 at any time for the full list of keyboard\n"
            "shortcuts.\n\n"
            "If you are unsure where to start, try browsing your\n"
            "own Documents folder first. Then, when you have a\n"
            "server ready, connect to it.\n\n"
            "Thank you for using SA Access Archive."
        )

        label = wx.StaticText(panel, label=welcome_text)
        sizer.Add(label, 1, wx.ALL | wx.EXPAND, 20)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK, "Begin")
        button_sizer.AddButton(ok_button)
        button_sizer.Realize()

        sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 15)

        panel.SetSizer(sizer)

        ok_button.SetFocus()


class SearchDialog(wx.Dialog):

    def __init__(self, parent):
        super().__init__(
            parent,
            title="Search",
            size=(500, 200)
        )

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(panel, label="Search for:")
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

        self.term_field = wx.TextCtrl(panel)
        sizer.Add(
            self.term_field, 0,
            wx.LEFT | wx.RIGHT | wx.EXPAND, 15
        )

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK, "Search")
        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()

        sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 15)

        panel.SetSizer(sizer)

        self.term_field.SetFocus()

    def get_term(self):
        return self.term_field.GetValue().strip()


class ServerSettingsDialog(wx.Dialog):

    def __init__(self, parent, address, username, password):
        super().__init__(
            parent,
            title="Server Settings",
            size=(600, 350)
        )

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        address_label = wx.StaticText(panel, label="Server address:")
        sizer.Add(address_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

        self.address_field = wx.TextCtrl(panel, value=address)
        sizer.Add(
            self.address_field, 0,
            wx.LEFT | wx.RIGHT | wx.EXPAND, 15
        )

        username_label = wx.StaticText(panel, label="Username:")
        sizer.Add(username_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

        self.username_field = wx.TextCtrl(panel, value=username)
        sizer.Add(
            self.username_field, 0,
            wx.LEFT | wx.RIGHT | wx.EXPAND, 15
        )

        password_label = wx.StaticText(panel, label="Password:")
        sizer.Add(password_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

        self.password_field = wx.TextCtrl(
            panel, value=password, style=wx.TE_PASSWORD
        )
        sizer.Add(
            self.password_field, 0,
            wx.LEFT | wx.RIGHT | wx.EXPAND, 15
        )

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK, "Save")
        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()

        sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 15)

        panel.SetSizer(sizer)

        self.address_field.SetFocus()

    def get_address(self):
        return self.address_field.GetValue().strip()

    def get_username(self):
        return self.username_field.GetValue().strip()

    def get_password(self):
        return self.password_field.GetValue()


def main():
    app = wx.App(False)
    MainWindow()
    app.MainLoop()


if __name__ == "__main__":
    main()