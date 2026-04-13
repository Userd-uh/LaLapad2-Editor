# LaLapad Gen2 Editor

LaLapad Gen2 向けの ZMK キーマップ GUI エディタです。  
ShiniNet さんが設計・公開しているキーボード「LaLapad Gen2」を対象にした補助ツールです。  
ブラウザ上でキーバインドを編集し、`.keymap` / `.conf` ファイルへ直接書き込みます。

## LaLapad Gen2 について

- LaLapad Gen2 は、ShiniNet さんによる独自設計のダブルトラックパッド搭載・分割ワイヤレスキーボードです
- キーボード本体の詳細や組み立て情報は、ShiniNet さんの公式リポジトリ / 頒布ページを参照してください
  - 公式リポジトリ: <https://github.com/ShiniNet/LaLaPadGen2>
  - 頒布ページ: <https://shininet.booth.pm/items/8039543>

## 機能

- **レイヤー編集** — 各レイヤーのキーバインドをクリックで変更
- **タップダンス** — シングルタップ / シングルホールド / ダブルタップの 3 動作を設定（最大 32 スロット）
- **マクロ** — キー操作のシーケンスを定義（最大 16 スロット）
- **コンボ** — 複数キーの同時押し設定
- **条件付きレイヤー** — `conditional_layers` の追加・編集
- **WSL 対応** — `\\wsl$\...` UNC パス上のファイルへ直接書き込み可能

## 必要環境

| 環境 | バージョン |
|------|----------|
| Python | 3.8 以上 |
| OS | Windows 10/11（WSL と組み合わせると ZMK ビルドまで一貫して行えます） |

## セットアップ

### 1. リポジトリを取得

```bash
git clone <このリポジトリの URL>
cd lalapad-gen2-editor
```

### 2. アプリを起動

**Windows の場合（ダブルクリックで起動）**

```
RunEditor.bat
```

**手動で起動する場合**

```bash
pip install flask
python app.py
```

起動するとブラウザが自動で `http://localhost:5173` を開きます。

> **注意（Windows）:** `RunEditor.bat` で開いたコマンドプロンプトのウィンドウはアプリ本体です。**このウィンドウを閉じるとアプリが終了し、保存ができなくなります。** 使用中は最小化にとどめてください。

### 3. ファームウェアフォルダを設定

1. ブラウザで開いた画面の「設定」タブを開く
2. ZMK config リポジトリのルートフォルダ（`config/*.keymap` が存在するフォルダの親）を指定する
3. 「読み込む」を押すとパスが自動検出されます

WSL 環境の場合は `\\wsl$\Ubuntu\home\<ユーザー名>\zmk-workspace\config\LaLapad_Gen2` のような UNC パスも指定できます。

> **注意:** 設定は `settings.json` に保存されます。このファイルには個人のパス情報が含まれるため、`.gitignore` で除外しています。

## カスタムモジュール（タップダンス triple 動作）

`module_templates/` フォルダに `zmk,behavior-tap-dance-triple` を提供する ZMK モジュールが含まれています。  
シングルタップ・シングルホールド・ダブルタップの 3 動作タップダンスを 1 件でも設定して `Save All` すると、アプリが `firmware_folder` 配下へ必要なモジュールを自動導入します。

- 導入先: `<firmware_folder>/remap_lalapad_tdq/` と `<firmware_folder>/zephyr/module.yml`
- 前提レイアウト: `<firmware_folder>/config`, `<firmware_folder>/boards`, `<firmware_folder>/zephyr`
- 安全策: 既存の同名ファイル内容がテンプレートと異なる場合は、自動導入も keymap 保存も中止します

### 自動導入で競合した場合

自動導入が止まった場合は、まず表示されたパスの既存ファイルを確認してください。  
手動で導入する場合は `module_templates/remap_lalapad_tdq/` を firmware ルートへ配置し、`zephyr/module.yml` に以下を反映します。

```yaml
build:
  settings:
    board_root: .
    dts_root: remap_lalapad_tdq
  cmake: remap_lalapad_tdq
  kconfig: remap_lalapad_tdq/Kconfig
```

従来どおり `config/west.yml` から取り込む運用を続けたい場合は、次のようにこのリポジトリを project として追加する方法も使えます。

```yaml
manifest:
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
    - name: your-remote
      url-base: https://github.com/<あなたのGitHubユーザー名>
  projects:
    - name: zmk
      remote: zmkfirmware
      revision: main
      import: app/west.yml
    - name: RemapLaLapadGen2          # このリポジトリ
      remote: your-remote
      revision: main
      path: modules/remap_lalapad_gen2
  self:
    path: config
```

## ファイル構成

```
RemapLaLapadGen2/
├── app.py                  # Flask バックエンド
├── templates/
│   └── index.html          # フロントエンド UI
├── module_templates/
│   ├── zephyr/
│   │   └── module.yml      # Zephyr モジュール定義
│   └── remap_lalapad_tdq/
│       ├── CMakeLists.txt
│       ├── Kconfig
│       ├── dts/bindings/behaviors/
│       │   └── zmk,behavior-tap-dance-triple.yaml
│       └── src/behaviors/
│           └── behavior_tap_dance_triple.c
├── requirements.txt        # Python 依存パッケージ
├── RunEditor.bat           # Windows 用起動スクリプト
└── settings.json.example   # 設定ファイルのテンプレート
```

## 使い方

### キーの変更

1. レイヤータブでレイヤーを選択
2. 変更したいキーをクリック
3. ポップアップでキーバインドを入力または選択
4. 「保存」ボタンで `.keymap` ファイルに書き込む

### タップダンスの設定

1. 「タップダンス」タブを開く
2. スロット番号ごとにシングルタップ / シングルホールド / ダブルタップを設定
3. キーマップ上で `&td0`、`&td1` ... として参照

### マクロの設定

1. 「マクロ」タブを開く
2. ステップを追加（press / release / tap / wait / テキスト入力）
3. キーマップ上で `&mc0`、`&mc1` ... として参照

> **マクロの保存先について:** マクロ定義（名前・ステップ内容）は `settings.json` にフォルダごとに保存されます。ファームウェアフォルダを切り替えると、そのフォルダ専用のマクロ設定が自動で読み込まれます（初回は空）。これは、マクロ名（display name）やテキスト入力ステップがキーマップファイルには保存できないためです。
