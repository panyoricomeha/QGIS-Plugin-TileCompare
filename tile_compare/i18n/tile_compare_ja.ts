<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="ja_JP">
<context>
    <name>TileCompare</name>
    <message>
        <source>Load Folder</source>
        <translation>フォルダ読み込み</translation>
    </message>
    <message>
        <source>Select the parent of the zoom level folders (any of 0-30).
Selecting a folder without tiles searches its subfolders.</source>
        <translation>ズームレベルフォルダ(0〜30 のどれでも)の親フォルダを選択。
タイル構成でないフォルダを選ぶとサブフォルダを一括検索します</translation>
    </message>
    <message>
        <source>Remove Selected</source>
        <translation>選択フォルダ取り消し</translation>
    </message>
    <message>
        <source>Remove the selected sources from the list and the map</source>
        <translation>選択した参照先を一覧と地図から取り除きます</translation>
    </message>
    <message>
        <source>Visible</source>
        <translation>表示</translation>
    </message>
    <message>
        <source>Name</source>
        <translation>名前</translation>
    </message>
    <message>
        <source>Zoom</source>
        <translation>ズーム</translation>
    </message>
    <message>
        <source>Format</source>
        <translation>形式</translation>
    </message>
    <message>
        <source>White transparent</source>
        <translation>白透過</translation>
    </message>
    <message>
        <source>Zoom to Selected</source>
        <translation>選択レイヤの範囲にズーム</translation>
    </message>
    <message>
        <source>Import XY Attribute Table</source>
        <translation>XY属性テーブルの取り込み</translation>
    </message>
    <message>
        <source>Turn an attribute table with x / y columns (database, TSV, CSV, clipboard)
into points in the project CRS, linked to the tile images under them</source>
        <translation>x / y 列のある属性テーブル（DB・TSV・CSV・クリップボード）を
プロジェクトの座標系の点にして、各点が載るタイル画像を紐づけます</translation>
    </message>
    <message>
        <source>e.g. 5-20</source>
        <translation>例: 5-20</translation>
    </message>
    <message>
        <source>Make white margins transparent so layers below show through</source>
        <translation>白い余白を透過して下のレイヤを見えるようにする</translation>
    </message>
    <message>
        <source>Could not create a layer: {path}</source>
        <translation>レイヤを作成できませんでした: {path}</translation>
    </message>
    <message>
        <source>Project CRS set to {authid} ({name}). Tiles are reprojected to it.</source>
        <translation>プロジェクトの座標系を {authid}（{name}）にしました。タイルはこの座標系に再投影して表示します</translation>
    </message>
    <message>
        <source>Enter zoom as "5-20"</source>
        <translation>ズームは「5-20」の形式で入力してください</translation>
    </message>
    <message>
        <source>File extension</source>
        <translation>拡張子</translation>
    </message>
    <message>
        <source>Loaded {n}</source>
        <translation>{n} 件読み込みました</translation>
    </message>
    <message>
        <source>({n} already loaded were skipped)</source>
        <translation>（読み込み済み {n} 件はスキップ）</translation>
    </message>
    <message>
        <source>Check "Visible" to add them to the map</source>
        <translation>「表示」にチェックすると地図に追加されます</translation>
    </message>
    <message>
        <source>Select a source folder (parent of the zoom level folders)</source>
        <translation>参照先フォルダ（ズームレベルフォルダの親）を選択</translation>
    </message>
    <message>
        <source>No zoom level folder structure such as {z}/{x}/{y}.png was found.</source>
        <translation>{z}/{x}/{y}.png のようなズームレベルフォルダ構成が見つかりませんでした。</translation>
    </message>
    <message>
        <source>Remove {n} source(s)?
(Their map layers are removed too. The folders are not deleted.)</source>
        <translation>{n} 件の参照先を取り消しますか？
（地図上のレイヤも削除されます。フォルダ自体は消えません）</translation>
    </message>
    <message>
        <source>Importing XY attribute table... {percent}% (QGIS stays usable)</source>
        <translation>XY属性テーブルを取り込んでいます… {percent}%（この間も QGIS は操作できます）</translation>
    </message>
    <message>
        <source>Importing XY attribute table...</source>
        <translation>XY属性テーブルを取り込んでいます…</translation>
    </message>
    <message>
        <source>Failed to import the XY attribute table: {error}</source>
        <translation>XY属性テーブルの取込に失敗しました: {error}</translation>
    </message>
    <message>
        <source>Import of the XY attribute table was canceled</source>
        <translation>XY属性テーブルの取込を中止しました</translation>
    </message>
    <message>
        <source>Imported {n} points (with tile image: {linked})</source>
        <translation>{n} 点を取り込みました（タイル画像あり {linked} 点）</translation>
    </message>
    <message>
        <source>{n} rows have no valid position</source>
        <translation>座標不明 {n} 行</translation>
    </message>
    <message>
        <source>No points overlap the images. Check the source CRS and the X / Y columns.</source>
        <translation>画像と重なる点がありません。元の座標系・X/Y 列の指定を確認してください</translation>
    </message>
    <message>
        <source>Import XY attribute table: {name}</source>
        <translation>XY属性テーブルの取込: {name}</translation>
    </message>
    <message>
        <source>Coordinates exceed ±300 km. The source CRS may be wrong. Use longitude/latitude columns (such as l / b) if available.</source>
        <translation>座標値が ±300km を超えています。元の座標系の指定が違う可能性があります。緯度経度の列（l / b など）があればそちらを使ってください</translation>
    </message>
    <message>
        <source>XY attribute table</source>
        <translation>XY属性テーブル</translation>
    </message>
    <message>
        <source>Database</source>
        <translation>データベース</translation>
    </message>
    <message>
        <source>TSV / CSV file (UTF-8 or Shift_JIS)</source>
        <translation>TSV / CSV ファイル（UTF-8 または Shift_JIS）</translation>
    </message>
    <message>
        <source>Browse…</source>
        <translation>参照…</translation>
    </message>
    <message>
        <source>From Clipboard</source>
        <translation>クリップボードから</translation>
    </message>
    <message>
        <source>Import a table copied from Excel or a database tool (with a header row)</source>
        <translation>Excel や DB ツールからコピーした表（見出し行付き）を取り込みます</translation>
    </message>
    <message>
        <source>File / Clipboard</source>
        <translation>ファイル / クリップボード</translation>
    </message>
    <message>
        <source>Treat the X column as north (vertical)</source>
        <translation>X 列を北方向（縦）として扱う</translation>
    </message>
    <message>
        <source>Survey coordinates use X for north and Y for east. Check this if the points look rotated by 90°.</source>
        <translation>測量座標は X が北・Y が東です。点が 90° 回ったような配置になる場合にチェック</translation>
    </message>
    <message>
        <source>X column</source>
        <translation>X 列</translation>
    </message>
    <message>
        <source>Y column</source>
        <translation>Y 列</translation>
    </message>
    <message>
        <source>Source CRS</source>
        <translation>元の座標系</translation>
    </message>
    <message>
        <source>Label column</source>
        <translation>ラベル列</translation>
    </message>
    <message>
        <source>Import</source>
        <translation>取込</translation>
    </message>
    <message>
        <source>SELECT * FROM ... (WHERE can be used to filter)</source>
        <translation>SELECT * FROM ...（WHERE で絞り込みも可）</translation>
    </message>
    <message>
        <source>Refresh connections (add connections in the Browser panel)</source>
        <translation>接続一覧を更新（接続はブラウザパネルで追加します）</translation>
    </message>
    <message>
        <source>Load</source>
        <translation>読込</translation>
    </message>
    <message>
        <source>Connection</source>
        <translation>接続</translation>
    </message>
    <message>
        <source>Schema</source>
        <translation>スキーマ</translation>
    </message>
    <message>
        <source>Table</source>
        <translation>テーブル</translation>
    </message>
    <message>
        <source>Cannot get database connections: {error}</source>
        <translation>データベース接続を取得できません: {error}</translation>
    </message>
    <message>
        <source>(No connections: add a database connection in the Browser panel)</source>
        <translation>(接続なし：ブラウザパネルで DB 接続を追加してください)</translation>
    </message>
    <message>
        <source>Cannot get schemas: {error}</source>
        <translation>スキーマ一覧を取得できません: {error}</translation>
    </message>
    <message>
        <source>Cannot get tables: {error}</source>
        <translation>テーブル一覧を取得できません: {error}</translation>
    </message>
    <message>
        <source>Specify a connection and SQL</source>
        <translation>接続と SQL を指定してください</translation>
    </message>
    <message>
        <source>SQL failed:
{error}</source>
        <translation>SQL の実行に失敗しました:
{error}</translation>
    </message>
    <message>
        <source>Open XY Attribute Table</source>
        <translation>XY属性テーブルを開く</translation>
    </message>
    <message>
        <source>Tables (*.tsv *.csv *.txt);;All files (*.*)</source>
        <translation>表 (*.tsv *.csv *.txt);;すべて (*.*)</translation>
    </message>
    <message>
        <source>(None)</source>
        <translation>(なし)</translation>
    </message>
    <message>
        <source>x / y appear to be projected with zone {zone} ({authid}) instead of the prefecture's zone {pref_zone}; the source CRS was set accordingly.</source>
        <translation>x / y は本来の {pref_zone} 系ではなく {zone} 系（{authid}）で変換された値と判定し、元の座標系をそれに設定しました</translation>
    </message>
    <message>
        <source>Load from a database, or import a table from a file or the clipboard.</source>
        <translation>データベースから読み込むか、ファイル / クリップボードから表を取り込んでください</translation>
    </message>
    <message>
        <source>Showing the first {n} rows (all rows are read in the background on import)</source>
        <translation>先頭 {n} 行を表示（取込時に全件をバックグラウンドで読み込みます）</translation>
    </message>
    <message>
        <source>{n} rows</source>
        <translation>{n} 行</translation>
    </message>
    <message>
        <source>First row ({authid}): {x}, {y}</source>
        <translation>1 行目の座標（{authid}）: {x}, {y}</translation>
    </message>
    <message>
        <source>Specify a table and the X / Y columns</source>
        <translation>表と X / Y 列を指定してください</translation>
    </message>
    <message>
        <source>Specify the source CRS</source>
        <translation>元の座標系を指定してください</translation>
    </message>
</context>
</TS>
