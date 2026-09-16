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
SOUND_ADD = (750, 120)
SOUND_REMOVE = (550, 120)
SOUND_QUEUE_ADD = (800, 100)

DEEP_SEARCH_LIMIT = 5000


# ---------- Download queue ----------

class QueueItem:
    """One file waiting in (or moving through) the download queue."""

    def __init__(self, remote_path, local_path):
        self.remote_path = remote_path
        self.local_path = local_path
        self.name = os.path.basename(local_path)
        self.status = "Waiting"

    def display(self):
        return self.status + "  -  " + self.name


class DownloadQueue:
    """Holds the items and coordinates the background worker."""

    def __init__(self, on_item_started, on_item_finished,
                 on_item_failed, on_queue_changed):
        self.items = []
        self.current_index = -1
        self.lock = threading.Lock()
        self.running = False
        self.on_item_started = on_item_started
        self.on_item_finished = on_item_finished
        self.on_item_failed = on_item_failed
        self.on_queue_changed = on_queue_changed

    def add(self, remote_path, local_path):
        item = QueueItem(remote_path, local_path)
        with self.lock:
            self.items.append(item)
        self.on_queue_changed()
        return item

    def remove(self, index):
        with self.lock:
            if index < 0 or index >= len(self.items):
                return
            item = self.items[index]
            if item.status == "Downloading":
                return
            del self.items[index]
        self.on_queue_changed()

    def clear_completed(self):
        with self.lock:
            self.items = [i for i in self.items if i.status != "Done"]
        self.on_queue_changed()

    def count(self):
        with self.lock:
            return len(self.items)

    def snapshot(self):
        with self.lock:
            return list(self.items)

    def next_waiting_index(self):
        with self.lock:
            for i, item in enumerate(self.items):
                if item.status == "Waiting":
                    return i
        return -1

    def start_next(self, client):
        """Kick off the next waiting item, if any."""
        if self.running:
            return

        index = self.next_waiting_index()
        if index == -1:
            return

        item = self.items[index]
        item.status = "Downloading"
        self.current_index = index
        self.running = True
        self.on_item_started(index, item)
        self.on_queue_changed()

        thread = threading.Thread(
            target=self.worker,
            args=(client, item),
            daemon=True
        )
        thread.start()

    def worker(self, client, item):
        try:
            client.download_sync(
                remote_path=item.remote_path,
                local_path=item.local_path
            )
            item.status = "Done"
            self.running = False
            wx.CallAfter(self.on_item_finished, item)
        except Exception as error:
            item.status = "Failed"
            self.running = False
            wx.CallAfter(self.on_item_failed, item, str(error))
        finally:
            wx.CallAfter(self.on_queue_changed)


# ---------- Main window ----------

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
        self.search_active = False

        self.queue_window = None

        self.queue = DownloadQueue(
            on_item_started=self.on_queue_item_started,
            on_item_finished=self.on_queue_item_finished,
            on_item_failed=self.on_queue_item_failed,
            on_queue_changed=self.on_queue_changed
        )

        self.build_menu_bar()
        self.build_body()

        self.Centre()
        self.Show()

        self.focus_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_focus_timer, self.focus_timer)
        self.focus_timer.Start(200, oneShot=True)

        self.load_local_folder(self.current_folder)
        self.play_sound(SOUND_LAUNCH)

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
        file_menu.Append(4005, "Queue Selected\tQ")
        file_menu.Append(4006, "Download Queue\tCtrl+Shift+Q")
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
        nav_menu.Append(3007, "Toggle Favourite\tB")
        nav_menu.Append(3008, "Favourites\tCtrl+B")
        nav_menu.AppendSeparator()
        nav_menu.Append(3004, "Search\tCtrl+F")
        nav_menu.Append(3006, "Deep Search\tCtrl+Shift+F")
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
        help_menu.Append(6001, "Help\tF1")
        help_menu.Append(6002, "Keyboard Shortcuts")
        menu_bar.Append(help_menu, "Help")

        about_menu = wx.Menu()
        about_menu.Append(7001, "About SA Access Archive")
        menu_bar.Append(about_menu, "About")

        self.SetMenuBar(menu_bar)

        self.Bind(wx.EVT_MENU, self.on_refresh, id=4001)
        self.Bind(wx.EVT_MENU, self.on_download_selected, id=4003)
        self.Bind(wx.EVT_MENU, self.on_queue_selected, id=4005)
        self.Bind(wx.EVT_MENU, self.on_show_queue, id=4006)
        self.Bind(wx.EVT_MENU, self.on_open_download_folder, id=4004)
        self.Bind(wx.EVT_MENU, self.on_quit, id=4002)
        self.Bind(wx.EVT_MENU, self.on_up_level, id=3001)
        self.Bind(wx.EVT_MENU, self.on_home, id=3002)
        self.Bind(wx.EVT_MENU, self.on_end, id=3003)
        self.Bind(wx.EVT_MENU, self.on_show_info, id=3005)
        self.Bind(wx.EVT_MENU, self.on_toggle_favourite, id=3007)
        self.Bind(wx.EVT_MENU, self.on_show_favourites, id=3008)
        self.Bind(wx.EVT_MENU, self.on_search, id=3004)
        self.Bind(wx.EVT_MENU, self.on_deep_search, id=3006)
        self.Bind(wx.EVT_MENU, self.on_server_settings, id=5006)
        self.Bind(wx.EVT_MENU, self.on_connect, id=5007)
        self.Bind(wx.EVT_MENU, self.on_disconnect, id=5008)
        self.Bind(wx.EVT_MENU, self.on_set_download_folder, id=5002)
        self.Bind(wx.EVT_MENU, self.on_set_start_folder, id=5003)
        self.Bind(wx.EVT_MENU, self.on_toggle_sounds, id=5005)
        self.Bind(wx.EVT_MENU, self.on_show_welcome_again, id=5010)
        self.Bind(wx.EVT_MENU, self.on_reset_settings, id=5004)
        self.Bind(wx.EVT_MENU, self.on_help, id=6001)
        self.Bind(wx.EVT_MENU, self.on_keyboard_shortcuts, id=6002)
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

    def get_selected_full_path(self):
        name = self.get_selected_name()
        if name is None:
            return None, None
        if self.remote_mode:
            full = self.remote_path.rstrip("/") + "/" + name
            return ("REMOTE", full)
        else:
            full = os.path.join(self.current_folder, name)
            return ("LOCAL", full)

    # ---------- Favourites ----------

    def get_favourites_list(self):
        raw = settings.get(self.config, "favourites")
        if not raw:
            return []
        entries = []
        for part in raw.split(";"):
            part = part.strip()
            if "|" in part:
                kind, path = part.split("|", 1)
                entries.append((kind.strip(), path.strip()))
        return entries

    def save_favourites_list(self, entries):
        parts = []
        for kind, path in entries:
            parts.append(kind + "|" + path)
        settings.set_value(self.config, "favourites", ";".join(parts))

    def is_favourite(self, kind, path):
        for k, p in self.get_favourites_list():
            if k == kind and p == path:
                return True
        return False

    def on_toggle_favourite(self, event):
        kind, path = self.get_selected_full_path()
        if kind is None:
            wx.MessageBox(
                "Nothing is selected.",
                "Favourite",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        entries = self.get_favourites_list()

        if self.is_favourite(kind, path):
            entries = [(k, p) for (k, p) in entries
                       if not (k == kind and p == path)]
            self.save_favourites_list(entries)
            self.play_sound(SOUND_REMOVE)
            self.status_label.SetLabel(
                "Removed from favourites: " + path
            )
        else:
            entries.append((kind, path))
            self.save_favourites_list(entries)
            self.play_sound(SOUND_ADD)
            self.status_label.SetLabel(
                "Added to favourites: " + path
            )

        self.Layout()
        self.item_list.SetFocus()

    def on_show_favourites(self, event):
        entries = self.get_favourites_list()

        if not entries:
            wx.MessageBox(
                "You have no favourites yet.\n\n"
                "Focus on any folder or file and press B to add it.",
                "Favourites",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        dialog = FavouritesDialog(self, entries)
        result = dialog.ShowModal()
        if result == wx.ID_OK:
            chosen_kind, chosen_path = dialog.get_selected()
            dialog.Destroy()
            if chosen_kind is not None:
                self.jump_to_favourite(chosen_kind, chosen_path)
        elif result == FavouritesDialog.ID_DELETE:
            new_entries = dialog.get_entries()
            self.save_favourites_list(new_entries)
            dialog.Destroy()
            self.play_sound(SOUND_REMOVE)
            self.status_label.SetLabel(
                "Favourite removed. Reopen with Ctrl+B to see the list."
            )
            self.Layout()
        else:
            dialog.Destroy()

    def jump_to_favourite(self, kind, path):
        if kind == "LOCAL":
            if os.path.isdir(path):
                parent = os.path.dirname(path)
                if not parent or not os.path.isdir(parent):
                    parent = path
                self.load_local_folder(parent)
                self.focus_item_in_list(os.path.basename(path))
            elif os.path.isfile(path):
                parent = os.path.dirname(path)
                self.load_local_folder(parent)
                self.focus_item_in_list(os.path.basename(path))
            else:
                wx.MessageBox(
                    "This favourite no longer exists:\n" + path,
                    "Not found",
                    wx.OK | wx.ICON_ERROR, self
                )
                return
            self.play_sound(SOUND_FOLDER)

        elif kind == "REMOTE":
            if self.remote_client is None:
                wx.MessageBox(
                    "Not connected to a server.\n\n"
                    "Connect first, then jump to the favourite.",
                    "Cannot jump",
                    wx.OK | wx.ICON_INFORMATION, self
                )
                return
            parent = os.path.dirname(path.rstrip("/"))
            if parent == "":
                parent = "/"
            self.load_remote_folder(parent)
            self.focus_item_in_list(os.path.basename(path.rstrip("/")))
            self.play_sound(SOUND_FOLDER)

        self.item_list.SetFocus()

    def focus_item_in_list(self, target_name):
        if not target_name:
            return
        count = self.item_list.GetItemCount()
        target_lower = target_name.lower()
        for i in range(count):
            name = self.item_list.GetItemText(i, 0)
            if name.lower() == target_lower:
                self.item_list.Focus(i)
                self.item_list.Select(i)
                return

    # ---------- Download queue ----------

    def on_queue_selected(self, event):
        self.queue_remote_file()

    def queue_remote_file(self):
        if not self.remote_mode:
            wx.MessageBox(
                "Queueing works for remote files only.\n\n"
                "Connect to a server first.",
                "Not in remote mode",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        name = self.get_selected_name()
        item_type = self.get_selected_type()
        if name is None or item_type != "Remote File":
            wx.MessageBox(
                "Select a remote file first.",
                "Nothing to queue",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        download_folder = settings.get(self.config, "download_folder")
        if not os.path.isdir(download_folder):
            wx.MessageBox(
                "The download folder does not exist:\n"
                + download_folder,
                "Cannot queue",
                wx.OK | wx.ICON_ERROR, self
            )
            return

        remote_path = self.remote_path.rstrip("/") + "/" + name
        local_path = os.path.join(download_folder, name)

        self.queue.add(remote_path, local_path)
        self.play_sound(SOUND_QUEUE_ADD)
        self.status_label.SetLabel(
            "Queued: " + name
            + "  (queue has " + str(self.queue.count()) + " items)"
        )
        self.Layout()

        if self.remote_client is not None:
            self.queue.start_next(self.remote_client)

    def on_download_selected(self, event):
        if not self.remote_mode:
            wx.MessageBox(
                "This option downloads files from a remote server.\n\n"
                "Connect to a server first.",
                "Not in remote mode",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        name = self.get_selected_name()
        item_type = self.get_selected_type()
        if name is None or item_type != "Remote File":
            wx.MessageBox(
                "Select a remote file first.",
                "Nothing to download",
                wx.OK | wx.ICON_INFORMATION, self
            )
            return

        if self.queue.running:
            self.queue_remote_file()
        else:
            self.queue_remote_file()

    def on_queue_item_started(self, index, item):
        self.status_label.SetLabel(
            "Downloading: " + item.name
            + "  (" + str(index + 1) + " of "
            + str(self.queue.count()) + " in queue)"
        )
        self.Layout()

    def on_queue_item_finished(self, item):
        self.play_sound(SOUND_DONE)
        self.status_label.SetLabel("Download complete: " + item.name)
        self.Layout()
        if self.remote_client is not None:
            self.queue.start_next(self.remote_client)

    def on_queue_item_failed(self, item, message):
        self.play_sound(SOUND_ERROR)
        self.status_label.SetLabel(
            "Download failed: " + item.name + "  -  " + message
        )
        self.Layout()
        if self.remote_client is not None:
            self.queue.start_next(self.remote_client)

    def on_queue_changed(self):
        if self.queue_window is not None:
            try:
                self.queue_window.refresh_list()
            except Exception:
                pass

    def on_show_queue(self, event):
        if self.queue_window is None:
            self.queue_window = QueueWindow(self, self.queue)
        else:
            self.queue_window.refresh_list()
        self.queue_window.Show()
        self.queue_window.Raise()

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

    # ---------- Search ----------

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

    def on_deep_search(self, event):
        if self.search_active:
            self.clear_search()
            return

        dialog = SearchDialog(self, title="Deep Search",
                              label="Deep search for:")
        if dialog.ShowModal() == wx.ID_OK:
            term = dialog.get_term()
            if term:
                self.apply_deep_search(term)
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

    def apply_deep_search(self, term):
        if self.remote_mode:
            self.apply_deep_search_remote(term)
        else:
            self.apply_deep_search_local(term)

    def apply_deep_search_local(self, term):
        lower = term.lower()
        matches = []
        truncated = False

        base = self.current_folder

        for root, dirs, files in os.walk(base):
            if truncated:
                break

            for name in dirs:
                if lower in name.lower():
                    full = os.path.join(root, name)
                    relative = os.path.relpath(full, base)
                    matches.append((relative, "Folder", "-"))
                    if len(matches) >= DEEP_SEARCH_LIMIT:
                        truncated = True
                        break

            if truncated:
                break

            for name in files:
                if lower in name.lower():
                    full = os.path.join(root, name)
                    relative = os.path.relpath(full, base)
                    try:
                        size_bytes = os.path.getsize(full)
                        size_text = self.format_size(size_bytes)
                    except OSError:
                        size_text = "?"
                    matches.append((relative, "File", size_text))
                    if len(matches) >= DEEP_SEARCH_LIMIT:
                        truncated = True
                        break

        self.show_deep_search_results(term, matches, truncated)

    def apply_deep_search_remote(self, term):
        if self.remote_client is None:
            wx.MessageBox(
                "Not connected to a server.",
                "Cannot search",
                wx.OK | wx.ICON_ERROR, self
            )
            return

        lower = term.lower()
        matches = []
        truncated = False

        base = self.remote_path if self.remote_path else "/"
        stack = [base]

        while stack and not truncated:
            path = stack.pop()
            try:
                entries = self.remote_client.list(path)
            except Exception:
                continue

            for entry in entries:
                clean = entry.rstrip("/")
                if clean == "" or clean == ".":
                    continue
                is_folder = entry.endswith("/")

                if lower in clean.lower():
                    if base == "/":
                        relative = clean
                    else:
                        full_path = path.rstrip("/") + "/" + clean
                        relative = os.path.relpath(full_path, base)
                        relative = relative.replace("\\", "/")
                    item_type = "Remote Folder" if is_folder else "Remote File"
                    size = "-" if is_folder else "?"
                    matches.append((relative, item_type, size))

                    if len(matches) >= DEEP_SEARCH_LIMIT:
                        truncated = True
                        break

                if is_folder:
                    new_path = path.rstrip("/") + "/" + clean
                    stack.append(new_path)

        self.show_deep_search_results(term, matches, truncated)

    def show_deep_search_results(self, term, matches, truncated):
        self.search_active = True
        self.item_list.DeleteAllItems()

        for name, item_type, size in matches:
            self.add_row(name, item_type, size)

        note = ""
        if truncated:
            note = "  (stopped at " + str(DEEP_SEARCH_LIMIT) + " results)"

        self.status_label.SetLabel(
            "Deep search results for '" + term + "': "
            + str(len(matches)) + " items" + note
            + "  (Backspace or Escape to clear)"
        )
        self.Layout()

        self.item_list.SetFocus()
        if self.item_list.GetItemCount() > 0:
            self.item_list.Focus(0)
            self.item_list.Select(0)
        else:
            wx.MessageBox(
                "No items found matching '" + term + "'.",
                "Deep Search",
                wx.OK | wx.ICON_INFORMATION, self
            )

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
        dialog = HelpDialog(self)
        dialog.ShowModal()
        dialog.Destroy()

    def on_keyboard_shortcuts(self, event):
        shortcuts = (
            "Keyboard shortcuts:\n\n"
            "Up and Down - move through the list\n"
            "Enter - open a folder, or download a remote file\n"
            "Backspace - go up one level\n"
            "Home - first item\n"
            "End - last item\n"
            "I - show info for the selected item\n"
            "B - add or remove the selected item from favourites\n"
            "Ctrl+B - open the favourites list\n"
            "Q - queue the selected remote file\n"
            "Ctrl+Shift+Q - open the download queue\n"
            "Letter or number - jump to the next item starting with it\n"
            "Ctrl+F - search the current folder\n"
            "Ctrl+Shift+F - deep search the folder and all subfolders\n"
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
            "Alt+A - About"
        )
        wx.MessageBox(
            shortcuts, "Keyboard Shortcuts",
            wx.OK | wx.ICON_INFORMATION,
            self
        )

    def on_about(self, event):
        wx.MessageBox(
            "SA Access Archive\n"
            "Version 1.6\n\n"
            "Developed by Raeez Kuhn, Eezo the Blind DJ\n"
            "Based in South Africa\n\n"
            "A South African accessible archive for blind and\n"
            "visually impaired users.",
            "About SA Access Archive",
            wx.OK | wx.ICON_INFORMATION,
            self
        )


class QueueWindow(wx.Frame):
    """A separate window showing the download queue."""

    def __init__(self, parent, queue):
        super().__init__(
            parent,
            title="Download Queue",
            size=(700, 500)
        )

        self.queue = queue

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        info = wx.StaticText(
            panel,
            label=("Press Delete on an item to remove it from the queue.\n"
                   "Press C to clear completed items.\n"
                   "Press Escape to close this window (the queue keeps running).")
        )
        sizer.Add(info, 0, wx.ALL, 10)

        self.status_label = wx.StaticText(panel, label="")
        sizer.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 10)

        self.list_box = wx.ListBox(panel, style=wx.LB_SINGLE)
        sizer.Add(self.list_box, 1, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
        button_sizer.Add(close_button, 0, wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        panel.SetSizer(sizer)

        self.panel = panel
        self.list_box.Bind(wx.EVT_KEY_DOWN, self.on_key)
        close_button.Bind(wx.EVT_BUTTON, self.on_close)

        self.refresh_list()

    def refresh_list(self):
        items = self.queue.snapshot()
        current_selection = self.list_box.GetSelection()

        self.list_box.Clear()
        for item in items:
            self.list_box.Append(item.display())

        if self.list_box.GetCount() > 0:
            if current_selection == -1 or current_selection >= self.list_box.GetCount():
                self.list_box.SetSelection(0)
            else:
                self.list_box.SetSelection(current_selection)

        if items:
            self.status_label.SetLabel(
                str(len(items)) + " item(s) in queue"
            )
        else:
            self.status_label.SetLabel("Queue is empty")

        self.Layout()

    def on_key(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_DELETE:
            index = self.list_box.GetSelection()
            if index != -1:
                self.queue.remove(index)
                self.refresh_list()
        elif key == ord("C") or key == ord("c"):
            self.queue.clear_completed()
            self.refresh_list()
        elif key == wx.WXK_ESCAPE:
            self.on_close(None)
        else:
            event.Skip()

    def on_close(self, event):
        self.Hide()


class FavouritesDialog(wx.Dialog):
    """List of favourites. Enter jumps, Delete removes."""

    ID_DELETE = wx.ID_HIGHEST + 1

    def __init__(self, parent, entries):
        super().__init__(
            parent,
            title="Favourites",
            size=(800, 500)
        )

        self.entries = list(entries)

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        info = wx.StaticText(
            panel,
            label=("Press Enter to jump to a favourite.\n"
                   "Press Delete to remove it from the list.")
        )
        sizer.Add(info, 0, wx.ALL, 10)

        self.list_box = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.populate()
        sizer.Add(self.list_box, 1, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        jump_button = wx.Button(panel, wx.ID_OK, "Jump")
        delete_button = wx.Button(panel, self.ID_DELETE, "Delete")
        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Close")
        button_sizer.AddButton(jump_button)
        button_sizer.AddButton(delete_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()

        sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        panel.SetSizer(sizer)

        self.list_box.SetFocus()
        if self.list_box.GetCount() > 0:
            self.list_box.SetSelection(0)

        self.list_box.Bind(wx.EVT_KEY_DOWN, self.on_key)

    def populate(self):
        self.list_box.Clear()
        for kind, path in self.entries:
            label = "[" + kind + "]  " + path
            self.list_box.Append(label)
        if self.list_box.GetCount() > 0:
            self.list_box.SetSelection(0)

    def on_key(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_DELETE:
            self.on_delete(None)
        elif key == wx.WXK_RETURN or key == wx.WXK_NUMPAD_ENTER:
            self.EndModal(wx.ID_OK)
        else:
            event.Skip()

    def on_delete(self, event):
        index = self.list_box.GetSelection()
        if index == -1:
            return
        del self.entries[index]
        self.populate()
        if self.list_box.GetCount() > 0:
            new_index = min(index, self.list_box.GetCount() - 1)
            self.list_box.SetSelection(new_index)
        else:
            self.EndModal(self.ID_DELETE)

    def get_selected(self):
        index = self.list_box.GetSelection()
        if index == -1 or index >= len(self.entries):
            return None, None
        return self.entries[index]

    def get_entries(self):
        return list(self.entries)


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
            "Version 1.6\n\n"
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
            "3. Search the current folder with Ctrl+F, or press\n"
            "Ctrl+Shift+F to search the folder and every subfolder\n"
            "below it.\n\n"
            "4. Mark items as favourites with the B key, and jump\n"
            "back to them with Ctrl+B.\n\n"
            "5. Queue remote files for download with the Q key, and\n"
            "view the queue with Ctrl+Shift+Q.\n\n"
            "6. Press F1 at any time for the full in-app guide.\n\n"
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


class HelpDialog(wx.Dialog):
    """The in-app guide shown when the user presses F1."""

    def __init__(self, parent):
        super().__init__(
            parent,
            title="SA Access Archive - Help",
            size=(800, 700)
        )

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        guide_text = (
            "SA Access Archive - Help\n"
            "\n"
            "About this application\n"
            "\n"
            "SA Access Archive is a Windows application for browsing\n"
            "and downloading files from accessible archives over the\n"
            "internet, and for browsing folders on your own computer.\n"
            "It is designed for blind and visually impaired users and\n"
            "works with screen readers such as NVDA, JAWS, and\n"
            "Narrator.\n"
            "\n"
            "Two modes\n"
            "\n"
            "The app has two modes: Local and Remote.\n"
            "\n"
            "Local mode shows the contents of a folder on your own\n"
            "computer. This is the mode you see when the app first\n"
            "opens.\n"
            "\n"
            "Remote mode shows the contents of an archive on a server\n"
            "somewhere on the internet. To use it, you first set the\n"
            "server address in Settings, then choose Connect to\n"
            "Server.\n"
            "\n"
            "The status line at the top of the window tells you which\n"
            "mode you are in. It says 'Local:' for local mode, and\n"
            "'Remote:' for remote mode.\n"
            "\n"
            "Moving around\n"
            "\n"
            "Use the Up and Down arrow keys to move through the list\n"
            "of items. Press Enter to open a folder. Press Backspace\n"
            "to go up one level. Press Home to jump to the first item\n"
            "and End to jump to the last item.\n"
            "\n"
            "To jump quickly to an item, press the first letter of\n"
            "its name. Press the same letter again to jump to the\n"
            "next item starting with that letter.\n"
            "\n"
            "Connecting to a remote archive\n"
            "\n"
            "1. Press Alt+S to open the Settings menu.\n"
            "2. Choose Server Settings.\n"
            "3. Enter the server address, username, and password.\n"
            "4. Choose Save.\n"
            "5. Press Alt+S again and choose Connect to Server.\n"
            "\n"
            "If the connection succeeds, the list is replaced with\n"
            "the contents of the remote archive, and the status line\n"
            "changes to 'Remote:'.\n"
            "\n"
            "If the connection fails, an error message appears and\n"
            "you stay in local mode.\n"
            "\n"
            "Downloading files\n"
            "\n"
            "There are two ways to download a remote file.\n"
            "\n"
            "Download now: press Enter on a remote file, or press\n"
            "Ctrl+D. If nothing is currently downloading, it starts\n"
            "immediately. If something is already downloading, the\n"
            "file is added to the download queue instead and waits\n"
            "its turn.\n"
            "\n"
            "Queue: press Q on a remote file to add it to the queue\n"
            "without downloading it right away.\n"
            "\n"
            "The download queue\n"
            "\n"
            "Press Ctrl+Shift+Q to open the download queue window.\n"
            "It shows every queued file and its status: Waiting,\n"
            "Downloading, Done, or Failed.\n"
            "\n"
            "In the queue window:\n"
            "- Press Delete on an item to remove it (not while downloading).\n"
            "- Press C to clear completed items.\n"
            "- Press Escape to close the window. The queue keeps running.\n"
            "\n"
            "The queue processes one file at a time, in order. When\n"
            "one finishes, the next starts automatically.\n"
            "\n"
            "To open your download folder in Windows Explorer, press\n"
            "Alt+F and choose Open Download Folder.\n"
            "\n"
            "Searching\n"
            "\n"
            "There are two kinds of search.\n"
            "\n"
            "Quick search: press Ctrl+F. It searches only the current\n"
            "folder. Fast, but limited.\n"
            "\n"
            "Deep search: press Ctrl+Shift+F. It searches the current\n"
            "folder and every subfolder below it, all the way down.\n"
            "Results include the full relative path to each item, so\n"
            "you can see where it lives in the tree.\n"
            "\n"
            "Deep search stops after 5000 results to keep things\n"
            "responsive. If that happens, the status line says so.\n"
            "\n"
            "Press Backspace or Escape to clear any search and\n"
            "return to the normal folder view.\n"
            "\n"
            "Favourites\n"
            "\n"
            "You can mark folders and files as favourites, so you\n"
            "can jump back to them quickly later.\n"
            "\n"
            "To add or remove the selected item from favourites,\n"
            "press B. A rising tone means it was added. A falling\n"
            "tone means it was removed.\n"
            "\n"
            "To see all your favourites, press Ctrl+B. A list opens\n"
            "showing every favourite with its full path. Press Enter\n"
            "on one to jump straight to it. Press Delete on one to\n"
            "remove it from the list.\n"
            "\n"
            "Favourites work in both local and remote mode. Local\n"
            "favourites are marked [LOCAL], remote ones [REMOTE].\n"
            "Favourites are saved, so they survive across restarts.\n"
            "\n"
            "Show info about a file\n"
            "\n"
            "Press I on any item to see its details: full path,\n"
            "size, dates, extension, and whether it is read only. In\n"
            "remote mode, the info also tells you where the file\n"
            "will be saved when downloaded.\n"
            "\n"
            "Sounds\n"
            "\n"
            "The app plays short tones to confirm actions. A high\n"
            "tone when the app starts. A soft click when a folder\n"
            "opens. A rising tone when a download finishes or a\n"
            "favourite is added. A falling tone when a favourite is\n"
            "removed. A medium tone when a file is queued. A low\n"
            "tone when something fails.\n"
            "\n"
            "To turn sounds on or off, press Alt+S and choose Toggle\n"
            "Sounds.\n"
            "\n"
            "Settings\n"
            "\n"
            "Press Alt+S to open the Settings menu. From there you\n"
            "can:\n"
            "\n"
            "- Set the server address, username, and password\n"
            "- Set the download folder\n"
            "- Set which folder opens on startup in local mode\n"
            "- Turn sounds on or off\n"
            "- Show the welcome screen again\n"
            "- Reset all settings to their defaults\n"
            "\n"
            "For the full list of keyboard shortcuts, press Alt+H\n"
            "and choose Keyboard Shortcuts.\n"
            "\n"
            "Getting help\n"
            "\n"
            "Press F1 at any time to bring up this guide.\n"
            "\n"
            "For questions, bug reports, or feature requests,\n"
            "contact the developer using the details in the About\n"
            "screen. Press Alt+A to open it."
        )

        self.text_field = wx.TextCtrl(
            panel,
            value=guide_text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        self.text_field.SetInsertionPoint(0)

        sizer.Add(self.text_field, 1, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        close_button = wx.Button(panel, wx.ID_OK, "Close")
        button_sizer.AddButton(close_button)
        button_sizer.Realize()

        sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(sizer)

        self.text_field.SetFocus()
        self.text_field.SetInsertionPoint(0)


class SearchDialog(wx.Dialog):

    def __init__(self, parent, title="Search", label="Search for:"):
        super().__init__(
            parent,
            title=title,
            size=(500, 200)
        )

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        label_widget = wx.StaticText(panel, label=label)
        sizer.Add(label_widget, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

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