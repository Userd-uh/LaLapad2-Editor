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
- **実機書き込み（ZMK Studio RPC）** — USB Serial / Bluetooth GATT 経由で、対応するキー割当をマイコンへ即時反映
- **フルファームウェア書き込み** — `Save All` 後に任意のビルドコマンドを実行し、生成済み UF2 をブートローダードライブへコピー
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

### マイコンへ書き込む

#### レイヤー上のキー割当だけを即時反映する

1. ファームウェアを `CONFIG_ZMK_STUDIO=y` かつ central 側に `snippet: studio-rpc-usb-uart` を含めてビルド/書き込みします
2. ヘッダー上部の `Connect USB` または `Connect Bluetooth` を押します
3. キーマップを編集後、ヘッダー上部の `Write keymap (RPC)` を押すと、ZMK Studio RPC でレイヤー上のキー割当だけを実機へ反映します

#### タップダンス、マクロ、コンボ、条件付きレイヤー、タッチパッド設定まで反映する

1. Device タブで `Build command`、`Build cwd`、`UF2 file`、`Flash target` を設定します
2. キーボードをブートローダーモードにして、UF2 ドライブを Windows にマウントします
3. ヘッダー上部の `Write firmware (UF2)` を押します

`Write firmware (UF2)` は、タップダンス、マクロ、コンボ、条件付きレイヤー、タッチパッドの `.conf` / Kconfig 設定を含めて `Save All` し、設定したビルドコマンドを実行して、生成された UF2 を指定ドライブへコピーします。ビルドコマンドでは `{firmware_folder}` と `{config_dir}` のプレースホルダーを使えます。

`Realtime keymap write` を有効にすると、編集後の短い待ち時間で接続中のマイコンへキー割当の差分を書き込みます。USB と Bluetooth のどちらも ZMK Studio RPC を使用します。Bluetooth はブラウザ/OS の Web Bluetooth 対応状況に依存します。

### タップダンスの設定

1. 「タップダンス」タブを開く
2. スロット番号ごとにシングルタップ / シングルホールド / ダブルタップを設定
3. キーマップ上で `&td0`、`&td1` ... として参照

### マクロの設定

1. 「マクロ」タブを開く
2. ステップを追加（press / release / tap / wait / テキスト入力）
3. キーマップ上で `&mc0`、`&mc1` ... として参照

> **マクロの保存先について:** マクロ定義（名前・ステップ内容）は `settings.json` にフォルダごとに保存されます。ファームウェアフォルダを切り替えると、そのフォルダ専用のマクロ設定が自動で読み込まれます（初回は空）。これは、マクロ名（display name）やテキスト入力ステップがキーマップファイルには保存できないためです。

## 注意事項

- このツールは LaLapad Gen2 向けの補助エディタであり、ZMK やキーボード本体の公式設定ツールではありません
- 書き込み先の `.keymap` / `.conf` / モジュール関連ファイルは直接更新されるため、利用前に対象ファイルや ZMK config リポジトリ全体のバックアップを取ることをおすすめします
- <span style="color: red; ">但し、デバイスへの反映はエディター上で表示されているキーに変更ではなくて、
エディタ上で変更した箇所がデバイスに反映されます。そのため、'.keymap'ファイルの内容とデバイスに記録されている内容が異なることがあります。</span>
- `settings.json` にはローカル環境のパス情報やマクロ定義が保存されます。公開リポジトリへ含めないよう、そのまま `.gitignore` から外さないでください
- 自動導入されるカスタムモジュールは、既存の ZMK ワークスペース構成や運用方法によっては競合する場合があります。競合メッセージが表示されたときは内容を確認してから手動で反映してください
- 保存後のビルド成否や実機での動作は、利用している ZMK のバージョン、追加モジュール、手元の設定内容に依存します。保存後は必ずビルドと実機確認を行ってください

## 免責事項

- このツールの利用によって生じた設定破損、ビルド失敗、キーマップ不整合、作業データの消失、その他いかなる損害についても、作者は責任を負いません
- LaLapad Gen2 本体、ZMK、ShiniNet さんの公開物とは別プロジェクトです。各公式情報やライセンス、利用条件はそれぞれの配布元・公開元を確認してください
- このツールは現状有姿で提供され、特定用途への適合性、継続的な動作、将来の互換性を保証しません
