import QtQuick
import QtQuick.Controls

Item {
    id: root
    property font font: Qt.font({family: Qt.platform.os === "windows" ? "Microsoft YaHei UI" : "Helvetica Neue", pixelSize: 13})
    property alias text: field.text
    property alias color: field.color
    property alias selectByMouse: field.selectByMouse
    property alias inputMethodHints: field.inputMethodHints
    property alias background: field.background
    property int renderType: TextInput.NativeRendering
    readonly property bool editing: field.activeFocus
    implicitWidth: 160
    implicitHeight: 40

    TextField {
        id: field
        objectName: "editor"
        width: root.width * 2
        height: root.height * 2
        scale: 0.5
        transformOrigin: Item.TopLeft
        font: Qt.font({family: root.font.family, pixelSize: root.font.pixelSize * 2,
                       weight: root.font.weight, italic: root.font.italic})
        renderType: root.renderType
    }
}
