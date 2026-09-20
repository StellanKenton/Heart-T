import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 900
    height: 570
    minimumWidth: 760
    minimumHeight: 520
    visible: true
    title: "Heart-T · 原始数据 CSV 采集测试"
    color: "#f2f4f8"
    font.pixelSize: 14
    font.family: Qt.platform.os === "windows" ? "Microsoft YaHei UI" : "Helvetica Neue"

    component SoftButton: Button {
        id: control
        property bool primary: false
        implicitHeight: 42
        leftPadding: 20
        rightPadding: 20
        opacity: enabled ? 1 : 0.45
        background: Rectangle {
            radius: 12
            color: control.down ? "#dce7f8" : (control.primary ? "#007aff" : "#edf2f9")
        }
        contentItem: Text {
            text: control.text
            color: control.primary ? "white" : "#007aff"
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    FileDialog {
        id: saveDialog
        title: "保存双通道原始数据"
        fileMode: FileDialog.SaveFile
        nameFilters: ["CSV 文件 (*.csv)"]
        currentFile: backend.suggestedFileName
        onAccepted: backend.saveCsv(selectedFile)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        Text {
            text: "双通道原始数据 CSV 采集"
            color: "#25334c"
            font.pixelSize: 25
            font.weight: Font.DemiBold
        }
        Text {
            text: "500 SPS / 通道 · 每个有效点逐行保存 · CH1 / CH2 均为原始 ADC 码"
            color: "#697589"
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 112
            radius: 20
            color: "white"
            border.color: "#e5e9f0"
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    ComboBox {
                        id: ports
                        Layout.fillWidth: true
                        model: backend.ports
                        textRole: "label"
                        valueRole: "port"
                        displayText: count ? currentText : "请选择 USB CDC 串口"
                    }
                    SoftButton { text: "刷新"; onClicked: backend.refreshPorts() }
                    SoftButton { text: "连接"; primary: true; enabled: ports.count > 0; onClicked: backend.connectPort(ports.currentValue) }
                    SoftButton { text: "断开"; onClicked: backend.disconnectPort() }
                }
                Text { text: backend.data.connectionStatus; color: "#697589"; Layout.fillWidth: true; elide: Text.ElideRight }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Repeater {
                model: [
                    ["已记录采样点", backend.data.sampleCount],
                    ["最新 CH1", backend.data.latest1],
                    ["最新 CH2", backend.data.latest2]
                ]
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 92
                    radius: 18
                    color: "white"
                    border.color: "#e5e9f0"
                    Column {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData[0]; color: "#697589"; font.pixelSize: 12 }
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData[1]; color: "#25334c"; font.pixelSize: 24; font.weight: Font.DemiBold }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 138
            radius: 20
            color: "white"
            border.color: "#e5e9f0"
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12
                RowLayout {
                    spacing: 12
                    SoftButton {
                        text: "开始"
                        primary: true
                        enabled: !backend.data.recording && !backend.data.canSave
                        onClicked: backend.startRecording()
                    }
                    SoftButton {
                        text: "结束"
                        enabled: backend.data.recording
                        onClicked: backend.stopRecording()
                    }
                    SoftButton {
                        text: "保存 CSV"
                        enabled: backend.data.canSave
                        onClicked: saveDialog.open()
                    }
                    Text {
                        text: backend.data.recording ? "● 正在记录" : (backend.data.canSave ? "记录已结束" : "等待开始")
                        color: backend.data.recording ? "#e04444" : "#697589"
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                }
                Text {
                    Layout.fillWidth: true
                    text: backend.data.message
                    color: "#697589"
                    elide: Text.ElideMiddle
                }
                Text {
                    Layout.fillWidth: true
                    text: "CSV 包含 start / sample / end；每个 sample 行含采样序号、时间、会话、帧序号、帧内点号和两路原始值。"
                    color: "#697589"
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }
        }
        Item { Layout.fillHeight: true }
    }
}
