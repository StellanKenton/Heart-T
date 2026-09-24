import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 1180
    height: 960
    minimumWidth: 860
    minimumHeight: 700
    visible: true
    title: "Heart-T · 双通道采集"
    color: "#f2f4f8"
    font.pixelSize: 13
    font.family: Qt.platform.os === "windows" ? "Microsoft YaHei UI" : "Helvetica Neue"
    property bool paused: false
    property var waveforms: JSON.parse(backend.waveforms)

    FileDialog {
        id: saveDialog
        title: "导出双通道原始数据"
        fileMode: FileDialog.SaveFile
        nameFilters: ["CSV 文件 (*.csv)"]
        currentFile: backend.suggestedFileName
        onAccepted: backend.saveCsv(selectedFile)
    }

    component SoftButton: Button {
        id: control
        property bool primary: false
        opacity: enabled ? 1 : 0.45
        implicitHeight: 40
        leftPadding: 18
        rightPadding: 18
        background: Rectangle {
            radius: 12
            color: control.down ? "#dce7f8" : (control.primary ? "#007aff" : "#edf2f9")
        }
        contentItem: HdText { renderType: Text.NativeRendering;
            text: control.text
            color: control.primary ? "white" : "#007aff"
            font.pixelSize: 13
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    ScrollView {
        id: scroll
        anchors.fill: parent
        anchors.margins: 20
        clip: true
        contentWidth: availableWidth
        ColumnLayout {
            width: scroll.availableWidth
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    HdText { renderType: Text.NativeRendering; text: "HEART / COSMOS"; color: "#007aff"; font.pixelSize: 11; font.letterSpacing: 3; font.weight: Font.DemiBold }
                    HdText { renderType: Text.NativeRendering; text: "双通道原始数据 · Wi-Fi TCP · 500 SPS / 通道"; color: "#697589"; font.pixelSize: 13 }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    radius: 14; color: "#e6efff"; implicitWidth: 126; implicitHeight: 36
                    HdText { renderType: Text.NativeRendering; anchors.centerIn: parent; text: window.paused ? "显示已暂停" : "RAW SIGNAL"; color: "#007aff"; font.pixelSize: 12; font.weight: Font.DemiBold }
                }
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 110
                radius: 22
                color: "white"
                border.color: "#e5e9f0"
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        HdInput {
                            id: hostInput
                            Layout.fillWidth: true
                            placeholderText: "输入 ESP32-S3 IP 地址"
                            color: "#25334c"
                            background: Rectangle { radius: 12; color: "#f2f4f8"; border.color: "#e5e9f0" }
                        }
                        ComboBox {
                            id: ports
                            Layout.preferredWidth: 260
                            model: backend.ports
                            textRole: "label"
                            valueRole: "port"
                            onActivated: hostInput.text = currentValue
                            delegate: ItemDelegate {
                                width: ports.width
                                implicitHeight: 40
                                highlighted: ports.highlightedIndex === index
                                contentItem: HdText {
                                    text: modelData.label
                                    font.pixelSize: 13
                                    color: "#25334c"
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                }
                            }
                            displayText: count ? currentText : "发现局域网设备"
                            implicitHeight: 40
                            background: Rectangle { radius: 12; color: "#f2f4f8"; border.color: "#e5e9f0" }
                            contentItem: HdText { renderType: Text.NativeRendering;
                                leftPadding: 12
                                rightPadding: 28
                                text: ports.displayText
                                    color: "#25334c"
                                font.pixelSize: 13
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }
                        }
                        SoftButton { text: "刷新"; onClicked: backend.refreshPorts() }
                        SoftButton { text: "连接"; primary: true; enabled: hostInput.text.trim().length > 0; onClicked: { window.paused = false; backend.connectPort(hostInput.text.trim()) } }
                        SoftButton { text: "断开"; onClicked: backend.disconnectPort() }
                        SoftButton { text: window.paused ? "继续显示" : "暂停显示"; onClicked: { window.paused = !window.paused; backend.setPaused(window.paused) } }
                    }
                    HdText { renderType: Text.NativeRendering; text: backend.data.status; color: "#697589"; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Repeater {
                    model: ["有效数据帧", "估计丢帧", "CRC 错误", "重复序号"]
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        implicitHeight: 76
                        radius: 18; color: "#e9edf4"
                        Column {
                            anchors.left: parent.left; anchors.leftMargin: 18
                            anchors.verticalCenter: parent.verticalCenter; spacing: 4
                            HdText { renderType: Text.NativeRendering; text: modelData; color: "#697589"; font.pixelSize: 11 }
                            HdText { renderType: Text.NativeRendering; text: [backend.data.frames, backend.data.missing, backend.data.crc, backend.data.duplicates][index]; color: "#25334c"; font.pixelSize: 22; font.weight: Font.DemiBold }
                        }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 116
                radius: 22
                color: "white"
                border.color: "#e5e9f0"
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        SoftButton {
                            text: "开始录制"
                            primary: true
                            enabled: !backend.recordingData.recording && !backend.recordingData.canSave
                            onClicked: backend.startRecording()
                        }
                        SoftButton {
                            text: "结束录制"
                            enabled: backend.recordingData.recording
                            onClicked: backend.stopRecording()
                        }
                        SoftButton {
                            text: "导出 CSV"
                            enabled: backend.recordingData.canSave
                            onClicked: saveDialog.open()
                        }
                        HdText {
                            text: "已记录 " + backend.recordingData.sampleCount + " 对原始采样"
                            color: "#25334c"
                            font.pixelSize: 13
                        }
                        Item { Layout.fillWidth: true }
                    }
                    HdText {
                        Layout.fillWidth: true
                        text: backend.recordingData.message || "录制所有收到的原始采样；结束后导出 CSV，暂停显示不影响录制。"
                        color: "#697589"
                        font.pixelSize: 12
                        elide: Text.ElideMiddle
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: axisControls.implicitHeight + 32
                radius: 22
                color: "white"
                border.color: "#e5e9f0"
                ColumnLayout {
                    id: axisControls
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Switch {
                            id: fitSwitch
                            text: "自动 Fit"
                            contentItem: HdText {
                                text: fitSwitch.text
                                font.pixelSize: 13
                                color: "#25334c"
                                leftPadding: fitSwitch.indicator.width + fitSwitch.spacing
                                verticalAlignment: Text.AlignVCenter
                            }
                            checked: backend.axis.autoFit
                            onClicked: { rangeError.text = ""; backend.setAutoFit(checked) }
                        }
                        HdText { renderType: Text.NativeRendering; text: "下限"; font.pixelSize: 13; color: "#25334c" }
                        HdInput {
                            id: lowerInput
                            objectName: "lowerInput"
                            Layout.preferredWidth: 170
                            enabled: !backend.axis.autoFit
                            text: backend.axis.lower.toString()
                            font.pixelSize: 13
                            renderType: TextInput.NativeRendering
                            selectByMouse: true
                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                            color: "#25334c"
                            background: Rectangle { radius: 20; color: "#f2f4f8"; border.color: lowerInput.editing ? "#007aff" : "#e5e9f0" }
                        }
                        HdText { renderType: Text.NativeRendering; text: "上限"; font.pixelSize: 13; color: "#25334c" }
                        HdInput {
                            id: upperInput
                            objectName: "upperInput"
                            Layout.preferredWidth: 170
                            enabled: !backend.axis.autoFit
                            text: backend.axis.upper.toString()
                            font.pixelSize: 13
                            renderType: TextInput.NativeRendering
                            selectByMouse: true
                            inputMethodHints: Qt.ImhFormattedNumbersOnly
                            color: "#25334c"
                            background: Rectangle { radius: 20; color: "#f2f4f8"; border.color: upperInput.editing ? "#007aff" : "#e5e9f0" }
                        }
                        SoftButton {
                            text: "应用"
                            enabled: !backend.axis.autoFit
                            primary: true
                            onClicked: rangeError.text = backend.setManualRange(lowerInput.text, upperInput.text)
                                       ? "" : "请输入有效数字，且上限必须大于下限"
                        }
                        Item { Layout.fillWidth: true }
                    }
                    HdText {
                        id: rangeError
                        renderType: Text.NativeRendering
                        visible: text.length > 0
                        color: "#d33b42"
                        font.pixelSize: 11
                    }
                }
            }
            Connections {
                target: backend
                function onAxisChanged() {
                    if (!lowerInput.editing) lowerInput.text = backend.axis.lower.toString()
                    if (!upperInput.editing) upperInput.text = backend.axis.upper.toString()
                }
            }
            RowLayout {
                HdText { text: "ECG 来源"; color: "#25334c"; font.pixelSize: 13 }
                ComboBox {
                    model: ["CH1", "CH2"]
                    currentIndex: backend.data.ecgChannel
                    enabled: !window.paused
                    onActivated: backend.setEcgChannel(currentIndex)
                }
                ComboBox {
                    model: ["基线稳定 · 0.5–40 Hz", "形态观察 · 0.05–40 Hz"]
                    currentIndex: backend.data.ecgMode
                    enabled: !window.paused
                    onActivated: backend.setEcgMode(currentIndex)
                }
                ComboBox {
                    id: ecgTime
                    model: ["5 秒", "2 秒", "1 秒"]
                    currentIndex: 1
                }
                HdText { text: "50 / 100 / 150 Hz 陷波"; color: "#697589"; font.pixelSize: 12 }
            }
            HdText {
                text: backend.data.ecgMode === 1
                      ? "形态观察保留更多低频；连接或切换通道后约 15 秒稳定，基线漂移会更明显。"
                      : "基线稳定适合观察节律；观察 P / T 细节可切换形态观察，并暂停、放大时间。"
                color: "#697589"; font.pixelSize: 12
            }
            Waveform { windowSamples: [2500, 1000, 500][ecgTime.currentIndex]; paused: window.paused; objectName: "filteredEcg"; channel: "ECG"; subtitle: "CH" + (backend.data.ecgChannel + 1) + " · 滤波显示"; accent: "#169c78"; samples: window.waveforms.ecg; latest: backend.data.latestEcg; lowerLimit: backend.data.ecgLower; upperLimit: backend.data.ecgUpper; independentAxis: true }
            Waveform { paused: window.paused; channel: "CH 01"; subtitle: "通道一"; accent: "#007aff"; samples: window.waveforms.ch1; latest: backend.data.latest1; lowerLimit: backend.axis.lower; upperLimit: backend.axis.upper; autoFit: backend.axis.autoFit }
            Waveform { paused: window.paused; channel: "CH 02"; subtitle: "通道二"; accent: "#af52de"; samples: window.waveforms.ch2; latest: backend.data.latest2; lowerLimit: backend.axis.lower; upperLimit: backend.axis.upper; autoFit: backend.axis.autoFit }
            HdText { renderType: Text.NativeRendering; text: "最近 5 秒 · 第一行滤波 ECG（可切换通道）· 后两行原始 ADC 码    /    暂停仅冻结显示，后台持续接收"; color: "#697589"; font.pixelSize: 11; Layout.alignment: Qt.AlignHCenter }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 280
                radius: 22
                color: "white"
                border.color: "#e5e9f0"
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8
                    HdText { text: "设备日志与命令行 · TCP 45671"; color: "#25334c"; font.pixelSize: 14; font.weight: Font.DemiBold }
                    HdText { text: backend.consoleStatus; color: "#697589"; font.pixelSize: 12 }
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        TextArea {
                            objectName: "deviceConsole"
                            readOnly: true
                            text: backend.consoleText
                            font.family: "Consolas"
                            font.pixelSize: 12
                            color: "#25334c"
                            wrapMode: TextEdit.NoWrap
                            selectByMouse: true
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        HdInput {
                            id: commandInput
                            Layout.fillWidth: true
                            placeholderText: "输入 help、status、time、version 或 reboot"
                            color: "#25334c"
                            onAccepted: { backend.sendCommand(text); text = "" }
                        }
                        SoftButton { text: "发送"; onClicked: { backend.sendCommand(commandInput.text); commandInput.text = "" } }
                    }
                }
            }
        }
    }
}
