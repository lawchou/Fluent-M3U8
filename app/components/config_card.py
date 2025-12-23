"""# coding:utf-8
import os
import re
from typing import List
from PySide6.QtCore import Qt, Signal, QTime

from PySide6.QtWidgets import QWidget, QHBoxLayout, QFileDialog

from qfluentwidgets import (IconWidget, BodyLabel, FluentIcon, InfoBarIcon, ComboBox,
                            PrimaryPushButton, LineEdit, GroupHeaderCardWidget, PushButton,
                            CompactSpinBox, SwitchButton, IndicatorPosition, PlainTextEdit,
                            ToolTipFilter, ConfigItem)

from m3u8.model import StreamInfo

from ..common.icon import Logo, PNG
from ..common.config import cfg
from ..common.concurrent import TaskExecutor
from ..common.utils import adjustFileName
from ..common.media_parser import MediaParser
from ..service.m3u8dl_service import M3U8DLCommand, m3u8Service, BatchM3U8FileParser


class M3U8GroupHeaderCardWidget(GroupHeaderCardWidget):

    def addSwitchOption(self, icon, title, content, command: M3U8DLCommand, configItem: ConfigItem):
        button = SwitchButton(self.tr("Off"), self, IndicatorPosition.RIGHT)
        button.setOnText(self.tr("On"))
        button.setOffText(self.tr("Off"))
        button.setProperty("command", command)
        button.setProperty("config", configItem)
        button.setChecked(cfg.get(configItem))
        button.checkedChanged.connect(lambda c: cfg.set(configItem, c))

        self.addGroup(icon, title, content, button)
        return button


class BasicConfigCard(GroupHeaderCardWidget):
    """ Basic config card """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(self.tr("Basic Settings"))
        self.mediaParser = None

        # use PlainTextEdit for multi-line input for URL and file name
        self.urlLineEdit = PlainTextEdit()
        self.fileNameLineEdit = PlainTextEdit()
        self.saveFolderButton = PushButton(self.tr("Choose"))
        self.threadCountSpinBox = CompactSpinBox()
        self.streamInfoComboBox = ComboBox()

        self.hintIcon = IconWidget(InfoBarIcon.INFORMATION, self)
        self.hintLabel = BodyLabel(
            self.tr("Click the download button to start downloading") + ' 👉')
        self.downloadButton = PrimaryPushButton(
            self.tr("Download"), self, FluentIcon.PLAY_SOLID)

        self.toolBarLayout = QHBoxLayout()

        self._initWidgets()

    def _initWidgets(self):
        self.setBorderRadius(8)

        self.streamInfoComboBox.setMinimumWidth(120)
        self.streamInfoComboBox.addItem(self.tr("Default"))

        self.downloadButton.setEnabled(False)
        self.hintIcon.setFixedSize(16, 16)

        # PlainTextEdit uses setFixedSize for width/height
        self.urlLineEdit.setFixedSize(300, 56)
        self.fileNameLineEdit.setFixedSize(300, 56)
        self.saveFolderButton.setFixedWidth(120)
        self.threadCountSpinBox.setFixedWidth(120)

        # placeholders and tooltips
        self.fileNameLineEdit.setPlaceholderText(self.tr("Please enter the name of downloaded file"))
        self.urlLineEdit.setPlaceholderText(self.tr("Please enter the path of m3u8, mpd or txt"))
        self.urlLineEdit.setToolTip(self.tr("The format of each line in the txt file is FileName,URL"))
        self.urlLineEdit.setToolTipDuration(3000)
        self.urlLineEdit.installEventFilter(ToolTipFilter(self.urlLineEdit))

        self.threadCountSpinBox.setRange(*cfg.threadCount.range)
        self.threadCountSpinBox.setValue(cfg.get(cfg.threadCount))

        self._initLayout()
        self._connectSignalToSlot()

    def _initLayout(self):
        # add widget to group
        self.addGroup(
            icon=Logo.GLOBE.icon(),
            title=self.tr("Download URL"),
            content=self.tr("The path of m3u8, mpd or txt file, support drag and drop txt file"),
            widget=self.urlLineEdit
        )
        self.addGroup(
            icon=Logo.FILM.icon(),
            title=self.tr("File Name"),
            content=self.tr("The name of downloaded file"),
            widget=self.fileNameLineEdit
        )
        self.addGroup(
            icon=Logo.PROJECTOR.icon(),
            title=self.tr("Stream Info"),
            content=self.tr("Select the stream to be downloaded"),
            widget=self.streamInfoComboBox
        )
        self.saveFolderGroup = self.addGroup(
            icon=Logo.FOLDER.icon(),
            title=self.tr("Save Folder"),
            content=cfg.get(cfg.saveFolder),
            widget=self.saveFolderButton
        )
        group = self.addGroup(
            icon=Logo.KNOT.icon(),
            title=self.tr("Download Threads"),
            content=self.tr("Set the number of concurrent download threads"),
            widget=self.threadCountSpinBox
        )
        group.setSeparatorVisible(True)

        # add widgets to bottom toolbar
        self.toolBarLayout.setContentsMargins(24, 15, 24, 20)
        self.toolBarLayout.setSpacing(10)
        self.toolBarLayout.addWidget(
            self.hintIcon, 0, Qt.AlignmentFlag.AlignLeft)
        self.toolBarLayout.addWidget(
            self.hintLabel, 0, Qt.AlignmentFlag.AlignLeft)
        self.toolBarLayout.addStretch(1)
        self.toolBarLayout.addWidget(
            self.downloadButton, 0, Qt.AlignmentFlag.AlignRight)
        self.toolBarLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.vBoxLayout.addLayout(self.toolBarLayout)

    def _onTextChanged(self):
        url = self.urlLineEdit.toPlainText().strip()
        fileName = self.fileNameLineEdit.toPlainText()
        if (m3u8Service.isSupport(url) and fileName) or url.endswith(".txt"):
            self.downloadButton.setEnabled(True)
        else:
            self.downloadButton.setEnabled(False)

    def _onUrlChanged(self, url: str):
        url = url.strip()
        if not m3u8Service.isSupport(url):
            self.mediaParser = None
            self._resetStreamInfo()
        else:
            self.mediaParser = MediaParser.parse(url)
            TaskExecutor.runTask(self.mediaParser.getStreamInfos).then(self._onStreamInfosFetched)

    def _onStreamInfosFetched(self, streamInfos: List[StreamInfo]):
        if not streamInfos:
            return self._resetStreamInfo()

        self.streamInfoComboBox.clear()

        for info in streamInfos:
            texts = []

            if info.resolution:
                w, h = info.resolution
                texts.append(self.tr("Resolution: ") + f"{w} × {h}")

            if info.codecs:
                texts.append(self.tr("Codecs: ") + info.codecs)

            if info.frame_rate is not None:
                texts.append(self.tr("Fps: ") + f"{info.frame_rate:.1f}")

            self.streamInfoComboBox.addItem("; ".join(texts), userData=info)

    def _chooseSaveFolder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Choose folder"), self.saveFolderGroup.content())

        if folder:
            folder = folder.replace("\\", "/")
            cfg.set(cfg.saveFolder, folder)
            self.saveFolderGroup.setContent(folder)

    def _resetStreamInfo(self):
        self.streamInfoComboBox.clear()
        self.streamInfoComboBox.addItem(self.tr("Default"))

    def _connectSignalToSlot(self):
        # PlainTextEdit.textChanged has no arguments so use lambdas to pass text
        self.urlLineEdit.textChanged.connect(lambda: self._onUrlChanged(self.urlLineEdit.toPlainText()))
        self.urlLineEdit.textChanged.connect(self._onTextChanged)
        self.fileNameLineEdit.textChanged.connect(self._onTextChanged)
        self.saveFolderButton.clicked.connect(self._chooseSaveFolder)
        self.threadCountSpinBox.valueChanged.connect(lambda v: cfg.set(cfg.threadCount, v))

    def parseOptions(self) -> List[List[str]]:
        """ Returns the m3u8dl options """
        result = []

        options = [
            M3U8DLCommand.SAVE_DIR.command(self.saveFolderGroup.content()),
            M3U8DLCommand.TMP_DIR.command(self.saveFolderGroup.content()),
            M3U8DLCommand.THREAD_COUNT.command(self.threadCountSpinBox.value()),
        ]

        if self.streamInfoComboBox.count() > 1:
            info = self.streamInfoComboBox.currentData()    # type: StreamInfo
            cmds = []

            if info.resolution:
                cmds.append(f'res="{info.resolution[0]}*"')

            if info.frame_rate:
                cmds.append(f'frame="{int(info.frame_rate)}*"')

            options.extend([
                M3U8DLCommand.SELECT_VIDEO.command(),
                ":".join(cmds)
            ])
        else:
            options.append(M3U8DLCommand.SELECT_VIDEO.command('best'))

        url = self.urlLineEdit.toPlainText().strip()
        if m3u8Service.isSupport(url):
            fileName = adjustFileName(self.fileNameLineEdit.toPlainText())
            result = [
                [url, M3U8DLCommand.SAVE_NAME.command(fileName), *options]
            ]
        else:
            tasks = BatchM3U8FileParser().parse(url)
            for fileName, m3u8Url in tasks:
                fileName = adjustFileName(fileName)
                result.append([
                    m3u8Url, M3U8DLCommand.SAVE_NAME.command(fileName), *options
                ])

        return result
"""
