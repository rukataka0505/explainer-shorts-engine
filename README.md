# 解説Shortsエンジン

実写・記録映像と音で説明する、ローカルのShorts制作エンジン。Codexが調査・素材選択・編集を担当し、Remotionで1080×1920へ仕上げる。

全文字幕はナレーションと同じ本文から表示する。固定のタイトル画面、図解、立ち絵は入れない。素材のいい瞬間を選び、画の切り替え・縦構図・現場音・声の間を編集する。[編集手順](docs/EDITING.md)と[根拠・設計判断](docs/SOURCES.md)を参照。

`project.json.editing` v1では、8つの編集パターンと16種の演出を意味・対象・時刻で指定できる。字幕の登場と強調、寄って戻るズーム、減衰シェイク、実際の映像の停止、B-roll、速度カーブ、SEを同じ時間軸へ展開する。原稿の変更に追従する発話参照、固定seed、実レンダーでの配置検査を備える。[演出の契約・制限](docs/EDITING_CONTRACT.md)を参照。

## 新しい編集をA/Bで確認する

```powershell
.\.venv\Scripts\python.exe examples/create_editing_demo.py
# 同じNASA原本がある場合は、上のコマンドに --source-project projects/aivisspeech-nise-sample
.\.venv\Scripts\python.exe tools/video.py prepare projects/editing-grammar-v1
.\.venv\Scripts\python.exe examples/create_editing_demo.py --align-baseline
.\.venv\Scripts\python.exe tools/video.py build projects/editing-grammar-v1 --quality preview
.\.venv\Scripts\python.exe tools/video.py wait projects/editing-grammar-v1
.\.venv\Scripts\python.exe tools/video.py review projects/editing-grammar-v1 --quality preview
.\.venv\Scripts\python.exe tools/video.py build projects/editing-grammar-v1-baseline --quality preview
.\.venv\Scripts\python.exe tools/video.py wait projects/editing-grammar-v1-baseline
.\.venv\Scripts\python.exe tools/video.py compare projects/editing-grammar-v1 --baseline projects/editing-grammar-v1-baseline
```

約30秒の実写・にせ音声。同じ9行の台本・同一の原音声・NASA素材で、小さい字幕・演出なしの版と比較する。A/Bは字幕のサイズ・改行も含む比較。発話前後の無音処理で尺が変わるため、原稿ボタンで同じ発話へ移動できる。比較HTMLはブラウザーで開き、A/Bの音を別々に再生する。確認・修正後は両案件を `--quality final` でbuildし、compareにも同じqualityを指定する。検証サンプルは投稿しない。

```powershell
# テンプレート一覧とJSON Schema
.\.venv\Scripts\python.exe tools/video.py catalog
.\.venv\Scripts\python.exe tools/video.py catalog --schema
```

比較HTMLをHTTPで開く場合は `.\.venv\Scripts\python.exe tools/review_server.py` を起動し、`http://127.0.0.1:8767/editing-grammar-v1/work/compare/index.html` を開く。ローカル専用で、動画の区間移動に必要なbyte-range配信に対応する。

## セットアップ

Python 3.13、Node.js、Git、FFmpeg/ffprobe。標準音声はAivisSpeechの「にせ」（ノーマル）。AivisSpeechを公式サイトから導入し、AivisHubの「にせ」を追加する。APIキー不要。

```powershell
.\tools\start_aivisspeech.ps1
.\.venv\Scripts\python.exe tools/video.py check --voices
```

接続先は`AIVISSPEECH_URL`（既定`http://127.0.0.1:10101`）、実行ファイルは`AIVISSPEECH_ENGINE`で指定できる。初回起動はモデルのダウンロードに数分かかる。
モデル: https://hub.aivis-project.com/aivm-models/6d11c6c2-f4a4-4435-887e-23dd60f8b8dd

「にせ」のAPI style_idは`1937616896`。配布ページ上のローカルStyle ID 0とは異なる。`check --voices`でAPIのIDを確認する。ElevenLabsを選ぶ案件だけELEVENLABS_API_KEYを設定する。

```powershell
$env:PYTHONUTF8 = '1'
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd ci --prefix remotion
.\.venv\Scripts\python.exe tools/video.py check
```

VOICEVOXを未導入なら `winget install --id HiroshibaKazuyuki.VOICEVOX -e`。`VOICEVOX_URL`、`VOICEVOX_ENGINE`、`VIDEO_FFMPEG`、`VIDEO_FFPROBE`で接続先・実行ファイルを指定できる。VOICEVOXを明示選択した時の接続先はlocalhost:50021。録音済み音声を使う案件はVOICEVOXなしでprepare/buildできる。

Remotion公式Agent Skillsは`.agents/skills/remotion-best-practices/`へ固定版を同梱。Remotion関連パッケージは同じバージョンに固定し、npmのlockfileを含む。

## まず実写サンプルを作る

```powershell
.\.venv\Scripts\python.exe examples/create_demo.py
.\.venv\Scripts\python.exe tools/video.py build projects/demo-water --quality preview
.\.venv\Scripts\python.exe tools/video.py wait projects/demo-water
.\.venv\Scripts\python.exe tools/video.py review projects/demo-water --quality preview
```

NASAの4K元映像3本を約720MBダウンロードし、別の同一打ち上げ記録から15秒の現場音を抽出する。完成した編集指定を使い、約24秒の「ロケットを守る、水の壁」を再現する。この旧サンプルはVOICEVOX:青山龍星を明示指定している。通常の既定音声はAivisSpeech / にせ。APIや配布ファイルはNASA側で変更される可能性がある。

`review`が返すHTMLを開くと、動画と各ショットの頭・中・末尾を見比べられる。画像を押すとその時刻へ移動する。これは編集確認用で、完成動画に文字や画像一覧が入ることはない。

## 普段の制作

音も台本と一緒に設計する。[音設計・24音のSE棚](docs/SOUND.md)を参照。`tools/video.py sounds --audition` で検索・試聴、`sounds projects/<案件> --use <音ID>` で取り込み、`sound-plan projects/<案件> --init` で採否の下書きを作れる。試聴棚の音は機械検査済みで、場面への採用前には試聴する。

Codexへ「○○の解説Shortsを作って」と依頼する。調査・台本・主要映像方針・声・納品方法を一度確認した後に制作する。「確認不要」で省略できる。

```powershell
# 素材を場面ごとに調べる（PySceneDetect）
.\.venv\Scripts\python.exe tools/selects.py projects/<案件>/assets/source.mp4 --out projects/<案件>/work/selects
# 音声生成と時間確定だけを実行
.\.venv\Scripts\python.exe tools/video.py prepare projects/<案件>
# 編集指定を更新してプレビュー
.\.venv\Scripts\python.exe tools/video.py build projects/<案件> --quality preview
.\.venv\Scripts\python.exe tools/video.py wait projects/<案件>
.\.venv\Scripts\python.exe tools/video.py review projects/<案件> --quality preview
# カットの前後を抜き出す
.\.venv\Scripts\python.exe tools/video.py inspect projects/<案件> --at 5 --duration 3
# 完成版
.\.venv\Scripts\python.exe tools/video.py build projects/<案件> --quality final
.\.venv\Scripts\python.exe tools/video.py wait projects/<案件>
.\.venv\Scripts\python.exe tools/video.py review projects/<案件> --quality final
```

buildは背景実行。waitは最長55秒待ち、終わっていなければもう一度waitする。失敗時は`work/job.log`を確認する。同じ案件の二重buildを避け、子プロセスをWindows Jobへ収容する。

## project.json

```json
{
  "title": "ロケットを守る、水の壁",
  "voices": {"narrator": {"provider": "aivisspeech", "style_id": 1937616896}},
  "beats": [{"id": "hook", "lines": [
    {"id": "q", "text": "この大量の水、何のためだと思う？", "gap": 0.2},
    {"id": "a", "text": "実は、ロケットを音から守っている。", "gap": 0.4}
  ]}],
  "shots": [
    {"id": "wide", "path": "assets/water.mp4", "source_start": 30,
     "to": {"line": "a", "offset": -0.15},
     "camera": [{"at": 0, "x": 0.53, "y": 0.6, "zoom": 1}]},
    {"id": "detail", "path": "assets/water.mp4", "source_start": 55,
     "from": {"line": "a", "offset": -0.15}}
  ],
  "audio": [{"path": "assets/water.mp4", "source_start": 30,
             "volume": 0.4, "duck": true, "fade_in": 0.1, "fade_out": 0.3}]
}
```

| 指定 | 意味 |
|---|---|
| beats / lines | 意味のまとまりと発話。idは全体で一意。音声実尺＋gapから時間を決める。無言beatはdurationを指定 |
| line.path | 録音音声の相対パス。指定時はTTSを呼ばない。textはその音声の実際の原稿を記す |
| voices / line.settings | 省略時はstyle.jsonのAivisSpeech音声。provider、voice_id、model_id、settingsを指定可。AivisSpeechはprovider: aivisspeechとstyle_id、VOICEVOXはprovider: voicevoxとstyle_id。設定は共通→声→発話の順 |
| from / to | 全体先頭からの秒数、または`{"line":"id","edge":"startまたはend","offset":秒}`。全beatの発話を参照可。from省略は0、to省略は末尾 |
| shots | 順番に並ぶ画。前のtoと次のfromを同じ参照でつなぎ、空白と重複を避ける。画像も使用可能 |
| source_start / speed | 素材内の開始秒と再生倍率。映像の速度変更を使う時は必要な動作を見極める。音トラックは独立 |
| camera | `at`はショット内の0..1。`x/y`は元画像の0..1。`zoom`はcover比の倍率、1以上。複数点で主役を追う。デフォルトは中心固定 |
| fit | coverが既定。全体を見る必要がある画のみcontain。camera.zoomと組み合わせ可能 |
| reason | 任意の短い編集意図。reviewに表示される |
| audio | 現場音、SE、音楽。映像ファイルの音声も指定可能。音量、フェード、duck、音楽のloopを設定 |
| research / youtube | 調査根拠・留保、YouTube説明欄とクレジット。これらのメタデータは作品内に描画しない |
| editing | version=1の演出指定。patternまたはeffect、reason、target、発話・ショット・単語に対する時刻、強度、SE。同じ正本の一部であり、派生する時間表へ追記しない |
| line.caption_path | 音声と同じ原文・実測文字時刻を持つRemotion Caption JSON。単語への正確な参照に使用。無音端の整理時も時刻を追従させる |
| shot.subject | 任意の重要範囲 `{x,y,width,height}`。元画像の0..1座標。ズーム後の見切れを検出する。自動顔検出ではない |

時刻をフレームへ一度確定してから描画する。元素材の音は映像側ではミュートされるため、使用時はaudioへ明示する。素材が短い場合はエラーにし、映像をループや静止で水増ししない。音源の長い末尾無音などは必要に応じてFFmpegで事前に整える。

選択した音素材が無音ならprepare/buildのwarningsで知らせる。音声トラックが存在するだけでは、効果音や現場音が実際に入っているとみなさない。

## 出力と検査

`output/preview.mp4`は540×960、`output/<タイトル>.mp4`は1080×1920。完成時に全文デコード、実尺、解像度、fps、48kHz、音量の実測を`output/final-validation.json`に保存する。約−16 LUFS、true peak −1.5 dBを運用目標とし、2パス補正後のAACを再測定する。

ミックス前に全トラックへ既定−6dBの余裕を設ける（style.audio.headroom_db）。補正前・補正後の両方でピークを検査し、補正前に余裕がなければ音量調整を求めて停止する。正規化で既に発生した歪みを隠さない。

映像の美しさ・台本の面白さは機械的合格とは別に、完成動画で確認する。主役の見切れ、場面との不一致、読み違いはproject.jsonや素材へ戻って直す。設定済み素材を高品質に実行するエンジンであり、題材を問わずヒットを保証する採点器は持たない。

## 非公開納品

納品が依頼範囲に含まれる場合に使う。

```powershell
.\.venv\Scripts\python.exe tools/video.py deliver projects/<案件>
```

`output/thumbnail.jpg`を用意する。文字が不要なら完成版の適切なフレームをFFmpegでJPEGへ取り出せる。既存のYouTube認証はリポジトリ外の`%LOCALAPPDATA%/VideoAutomationEngine/`を共有し、deliverはprivateで納品する。公開依頼がある場合は、納品完了後に`tools/video.py publish projects/<案件>`でpublicへ変更し、APIで再確認する。現在の原稿・MP4と検証結果の一致、YouTube処理完了、サムネイル設定成功まで確認する。

## 開発と保存

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
npm.cmd run typecheck --prefix remotion
npm.cmd test --prefix remotion
# トリム・速度・カット位置と独立音声を、実レンダーで検証（任意の統合検査）
.\.venv\Scripts\python.exe tests/render_smoke.py
# 16演出の実レンダー回帰（360×640。最後の2演出にはWebGL環境が必要）
.\.venv\Scripts\python.exe examples/create_editing_fixture.py
.\.venv\Scripts\python.exe tools/video.py build projects/editing-fixture-v1 --quality final
.\.venv\Scripts\python.exe tools/video.py wait projects/editing-fixture-v1
.\.venv\Scripts\python.exe tests/verify_editing_render.py
```

元エンジンから音声キャッシュ、背景ジョブ、検査と非公開納品を継承。新エンジンは元フォルダに依存せず動く。`projects/`、素材、生成動画、認証情報はGit対象外。`examples/`に再現用の編集指定と素材取得コードを残す。

回帰検査はフレーム位置・画素・実音声を調べ、38時点の縮小参照と比較する。参照を更新する時だけ `--update-reference` を指定し、生成される `output/editing-contact.jpg` を確認する。合成パターンの検査と、実写作品の良し悪しは別に評価する。[今回の実測・確認範囲](docs/VERIFICATION.md)。

## 音声と全文字幕

既定はAivisSpeech / にせ / ノーマル。Shorts向けにAivisSpeechの`speedScale`を1.2とし、VOICEVOX用の抑揚設定は混ぜない。設定はstyle.jsonのaivisspeech.settings→声→発話の順に上書きする。

ElevenLabs / Koji / eleven_multilingual_v2も選択可能。ElevenLabsの既定設定はstyle.jsonのelevenlabsへ分離。APIキーは環境変数のみから読む。
公開Voice LibraryのKoji（voice_id: W8wofKLOWnsM57L8hIx2）を自分の声一覧へ追加して使う。別の声はstyle.jsonのvoice、または案件のvoicesで指定する。checkは選択したサービスと声を確認し、--voicesで選択したサービスの声一覧を表示する。録音だけの案件はAPI接続不要。

字幕はbeats[].lines[].textから生成し、本文を要約・書き換えない。ElevenLabsのwith-timestamps APIが返す原文の文字時刻で長文のページを切り替える。原文と文字時刻が一致しない場合はエラー。AivisSpeech・VOICEVOX・録音素材は従来同様に発話全体の時間と文字数による分割のため、長い発話は短く分ける。生成音声の読み違いは試聴して直す。

元エンジンの日本語改行・保護単語とSubtitle描画を流用。既定はずんだもんと同じ緑 #66E07A・白内縁10px・黒外縁4px、帯なし。声とは独立した色設定。1080×1920基準のサイズ・位置をstyle.jsonのsubtitlesへ置き、案件のsubtitlesで上書きできる。字幕原稿は別に作らない。
既定サイズは88px、1行8文字・2行を出発点とし、強調語を途中で分割しない。保護語が長ければ幅に合わせて縮小する。safe_areaは各SNSの不変の規格ではなく、このエンジンの調整可能な余白。レンダー時の実際の文字配置で、縁取り・拡大後も画面内かを検査する。
音声は本文・声・モデル・設定を含むキャッシュで再利用し、字幕の配置変更だけでは再課金されない。

API仕様: https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps

検証用サンプルの再現:
```powershell
.\.venv\Scripts\python.exe examples/create_elevenlabs_demo.py
.\.venv\Scripts\python.exe tools/video.py build projects/elevenlabs-preview --quality preview
```

AivisSpeechサンプルの再現（NASA実写・約20秒）:
```powershell
.\.venv\Scripts\python.exe examples/create_aivisspeech_demo.py
.\.venv\Scripts\python.exe tools/video.py build projects/aivisspeech-nise-sample --quality preview
```
