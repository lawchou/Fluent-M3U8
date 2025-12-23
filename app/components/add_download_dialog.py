# coding:utf-8
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout

from qfluentwidgets import PushButton, PrimaryPushButton, FluentIcon, InfoBar, InfoBarPosition

from .config_card import BasicConfigCard
from ..service.m3u8dl_service import m3u8Service
from ..common.signal_bus import signalBus
from ..common.config import cfg


class AddDownloadDialog(QDialog):
    """ Dialog for adding new download task using Basic Settings """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("新增下载任务"))
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self.basicCard = BasicConfigCard(self)

        self.addButton = PrimaryPushButton(self.tr("添加"), self, FluentIcon.PLAY_SOLID)
        self.cancelButton = PushButton(self.tr("取消"), self)

        # layout
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.addWidget(self.basicCard)

        hBox = QHBoxLayout()
        hBox.addStretch(1)
        hBox.addWidget(self.cancelButton)
        hBox.addWidget(self.addButton)

        self.vBoxLayout.addLayout(hBox)

        # signals
        self.cancelButton.clicked.connect(self.close)
        self.addButton.clicked.connect(self._onAddClicked)

    def setDownloadLink(self, url: str):
        """ Set download URL into the dialog (used by drag-and-drop from Home) """
        try:
            self.basicCard.urlLineEdit.setPlainText(url)
        except Exception:
            # fallback if underlying widget is LineEdit
            try:
                self.basicCard.urlLineEdit.setText(url)
            except Exception:
                pass

    def _onAddClicked(self):
        # check availability
        if not m3u8Service.isAvailable():
            InfoBar.error(
                self.tr("Task failed"),
                self.tr("Please choose N_m3u8DL-RE binary file in setting interface"),
                duration=-1,
                position=InfoBarPosition.BOTTOM,
                parent=self
            )
            return

        basicOptions = self.basicCard.parseOptions()
        if not basicOptions:
            InfoBar.warning(
                self.tr("Task failed"),
                self.tr("No available tasks found, please check the format of txt"),
                duration=-1,
                position=InfoBarPosition.BOTTOM,
                parent=self
            )
            return

        success = True
        for basicOption in basicOptions:
            # Only use basic settings for dialog
            options = [*basicOption]
            success = m3u8Service.download(options, self.basicCard.mediaParser) and success

        button = PushButton(self.tr('Check'))

        if success:
            w = InfoBar.success(
                self.tr("Task created"),
                self.tr("Please check the download task"),
                duration=5000,
                position=InfoBarPosition.BOTTOM,
                parent=self
            )
            button.clicked.connect(signalBus.switchToTaskInterfaceSig)

            # clear inputs in dialog then close
            if cfg.get(cfg.autoResetLink):
                try:
                    self.basicCard.urlLineEdit.clear()
                    self.basicCard.fileNameLineEdit.clear()
                except Exception:
                    pass

            # close dialog after adding
            self.close()
        else:
            w = InfoBar.error(
                self.tr("Task failed"),
                self.tr("Please check the error log"),
                duration=-1,
                position=InfoBarPosition.BOTTOM,
                parent=self
            )
            button.clicked.connect(m3u8Service.showDownloadLog)

        w.widgetLayout.insertSpacing(0, 10)
        w.addWidget(button)
