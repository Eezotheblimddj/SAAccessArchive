

import os

import wx

import settings

APP_TITLE = "SA Access Archive - by Raeez Kuhn, Eezo the Blind DJ"


class MainWindow(wx.Frame):

    def __init__(self):
        super().__init__(parent=None, title=APP_TITLE, size=(900, 600))

        self.config = settings.load_settings()
        self.current_folder = settings.get(self.config, "start_folder")

        if not os.path.isdir(self.current_folder):
            self.current_folder = os.path.expanduser("~")

        self.build_menu_bar()
        self.build_body()

        self.Centre()
        self.Show()

        self.focus_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_focus_timer, self.focus_timer)
        self.focus_timer.Start(200, oneShot=True)

        self.load_folder(self.current_folder)

    def on_focus_timer(self, event):
        self.item_list.SetFocus()
        if self.item_list.GetItemCount() > 0:
            self.item_list.Focus(0)
            self.item_list.Select(0)

    def build_menu_bar(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        file_menu.Append(4001, "Refresh\tF5")
        file_menu.AppendSeparator()
        file_menu.Append(4002, "Quit\tCtrl+Q")
        menu_bar.Append(file_menu, "File")

        nav_menu = wx.Menu()
        nav_menu.Append(3001, "Up One Level\tBackspace")
        nav_menu.Append(3002, "Home\tHome")
        nav_menu.Append(3003, "End\tEnd")
        nav_menu.AppendSeparator()
        nav_menu.Append(3004, "Search\tCtrl+F")
        menu_bar.Append(nav_menu, "Navigate")

        settings_menu = wx.Menu()
        settings_menu.Append(5001, "Server Settings")
        settings_menu.Append(5002, "Set Download Folder")
        settings_menu.Append(5003, "Set Start Folder")
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
        self.Bind(wx.EVT_MENU, self.on_quit, id=4002)
        self.Bind(wx.EVT_MENU, self.on_up_level, id=3001)
        self.Bind(wx.EVT_MENU, self.on_home, id=3002)
        self.Bind(wx.EVT_MENU, self.on_end, id=3003)
        self.Bind(wx.EVT_MENU, self.on_placeholder, id=3004)
        self.Bind(wx.EVT_MENU, self.on_server_settings, id=5001)
        self.Bind(wx.EVT_MENU, self.on_set_download_folder, id=5002)
        self.Bind(wx.EVT_MENU, self.on_set_start_folder, id=5003)
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

    def load_folder(self, folder):
        self.current_folder = folder
        self.item_list.DeleteAllItems()

        try:
            entries = sorted(os.listdir(folder))
        except OSError as error:
            self.status_label.SetLabel("Could not read folder: " + str(error))
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
            folder + "  (" + str(total) + " items)"
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
            self.Close()
        elif key == wx.WXK_BACK:
            self.on_up_level(None)
        elif key == wx.WXK_HOME:
            self.on_home(None)
        elif key == wx.WXK_END:
            self.on_end(None)
        elif key == wx.WXK_RETURN or key == wx.WXK_NUMPAD_ENTER:
            self.open_selected()
        else:
            event.Skip()

    def on_item_activated(self, event):
        self.open_selected()

    def open_selected(self):
        name = self.get_selected_name()
        item_type = self.get_selected_type()

        if name is None or item_type is None:
            return

        full_path = os.path.join(self.current_folder, name)

        if item_type == "Folder":
            self.load_folder(full_path)
            self.item_list.SetFocus()
            if self.item_list.GetItemCount() > 0:
                self.item_list.Focus(0)
                self.item_list.Select(0)
        else:
            self.status_label.SetLabel(
                "File selected: " + name + "  (download not yet built)"
            )
            self.Layout()

    def on_up_level(self, event):
        parent = os.path.dirname(self.current_folder)
        if parent and parent != self.current_folder:
            self.load_folder(parent)
            self.item_list.SetFocus()
            if self.item_list.GetItemCount() > 0:
                self.item_list.Focus(0)
                self.item_list.Select(0)
        else:
            self.status_label.SetLabel("Already at the top level.")
            self.Layout()

    def on_refresh(self, event):
        self.load_folder(self.current_folder)
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

    def on_server_settings(self, event):
        current_address = settings.get(self.config, "server_address")
        current_user = settings.get(self.config, "server_username")

        message = (
            "Server settings\n\n"
            "Current server address:\n"
            + (current_address if current_address else "(not set)")
            + "\n\nCurrent username:\n"
            + (current_user if current_user else "(not set)")
            + "\n\nServer configuration will be added in a later build."
        )

        wx.MessageBox(
            message, "Server Settings",
            wx.OK | wx.ICON_INFORMATION, self
        )

    def on_set_start_folder(self, event):
        dialog = wx.DirDialog(
            self, "Choose the folder to open on startup",
            defaultPath=self.current_folder,
            style=wx.DD_DEFAULT_STYLE
        )
        if dialog.ShowModal() == wx.ID_OK:
            chosen = dialog.GetPath()
            settings.set_value(self.config, "start_folder", chosen)
            self.load_folder(chosen)
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

    def on_reset_settings(self, event):
        answer = wx.MessageBox(
            "Reset all settings to their defaults?",
            "Confirm reset",
            wx.YES_NO | wx.ICON_QUESTION, self
        )
        if answer == wx.YES:
            for key, value in settings.DEFAULTS.items():
                settings.set_value(self.config, key, value)
            self.load_folder(settings.get(self.config, "start_folder"))
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
            "Enter - open a folder or select a file\n"
            "Backspace - go up one level\n"
            "Home - first item\n"
            "End - last item\n"
            "Escape - close the application\n"
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
            "Version 0.4\n\n"
            "Developed by Raeez Kuhn, Eezo the Blind DJ\n"
            "Based in South Africa\n\n"
            "A South African accessible archive for blind and\n"
            "visually impaired users.",
            "About SA Access Archive",
            wx.OK | wx.ICON_INFORMATION,
            self
        )


def main():
    app = wx.App(False)
    MainWindow()
    app.MainLoop()


if __name__ == "__main__":
    main()