import QtQuick

Item {
    id: root
    property font font: Qt.font({family: Qt.platform.os === "windows" ? "Microsoft YaHei UI" : "Helvetica Neue", pixelSize: 13})
    property alias text: glyph.text
    property alias color: glyph.color
    property alias horizontalAlignment: glyph.horizontalAlignment
    property alias verticalAlignment: glyph.verticalAlignment
    property alias elide: glyph.elide
    property int renderType: Text.NativeRendering
    property real leftPadding: 0
    property real rightPadding: 0
    implicitWidth: glyph.implicitWidth / 2
    implicitHeight: glyph.implicitHeight / 2

    // Rasterize glyphs at twice the logical size, then display at 1x.
    Text {
        id: glyph
        width: root.width * 2
        height: root.height * 2
        scale: 0.5
        transformOrigin: Item.TopLeft
        font: Qt.font({family: root.font.family, pixelSize: root.font.pixelSize * 2,
                       weight: root.font.weight, italic: root.font.italic,
                       letterSpacing: root.font.letterSpacing * 2,
                       kerning: root.font.kerning})
        leftPadding: root.leftPadding * 2
        rightPadding: root.rightPadding * 2
        renderType: root.renderType
        antialiasing: true
    }
}
