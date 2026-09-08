# 演出の契約 v1

正本は `project.json`。既存のbeats・shots・audioに任意のediting節を追加する。編集意図からpatternを選び、effectへ展開し、RemotionとFFmpegで実行する。別の一行言語、外部編集ソフト、AIモデル呼び出しは不要。

`editing/templates.v1.json` が技法・組み合わせ・数値範囲の正本。数値配列は `[既定値, 最小値, 最大値]`。`tools/video.py catalog` で取得できる。`editing/schema.v1.json` はediting節専用のJSON Schemaで、`tools/editing_schema.py` がregistryから生成する。時刻・媒体・原稿はPython、文字の実配置はRemotionの描画時に検証する。

## 指定例

既存の発話answerとショットwaterに対する例。IDと音源は案件の実在するものへ置き換える。

```json
{
  "editing": {
    "version": 1,
    "seed": "my-video-v1",
    "caption_animation": "caption_pop",
    "sounds": {
      "soft_hit": {"path": "assets/hit.wav", "marker": 0, "volume": 0.25}
    },
    "events": [{
      "id": "unexpected-answer",
      "pattern": "emphasize_claim",
      "at": {"line": "answer", "offset": 1.2},
      "target": {"shot": "water", "line": "answer", "keyword": "音", "anchor": {"x": 0.45, "y": 0.5}},
      "intensity": 0.6,
      "intent": "emphasis",
      "emotion": "surprise",
      "importance": 0.85,
      "reason": "答えの中心である音へ、寄りと原稿の強調を合わせる",
      "audio": {"sfx": "soft_hit", "sync": "impact"}
    }]
  }
}
```

editing省略時は演出を自動追加しない。全ページの小さな字幕登場もcaption_animationで明示する。同じ動画へすべてのpatternを使う必要はない。

## 共通契約

| 指定 | 意味 |
|---|---|
| id / version | IDは一意の英数字・下線・ハイフン。技法versionは1。未対応版はエラー |
| effect / pattern | どちらか一つ。未知の名前・数値パラメータは無視しない |
| reason | 必須。その場面で使う理由。reviewにも表示 |
| intent / emotion / importance | 任意の意味情報。importanceは0..1。保存・再編集に使用。自動分類器は未実装 |
| intensity | 0..1、既定0.5。0は付属SEも含め無効。0.5がregistry基準、1は変位が基準の2倍 |
| params | 個別技法の数値設定。patternなら `{"punch_zoom":{"peak_scale":1.1}}` のように技法ごと |
| duration | 個別effectの秒数。patternは技法ごとの既定時間。異なる時間で組む場合は個別effectを指定 |
| seed / variation | seedの既定は案件seed＋ID。variationは既定0。明示した時だけ時間を最大±8%変化。SHA256と固定フレーム乱数を使用 |
| target | shot/lineは既存ID。keywordは原稿内の文字列。anchor/pointは完成画面の0..1座標。文字列faceの自動追跡はない |

倍率は `1 + (基準倍率 - 1) × intensity / 0.5`、画面上のpxは `基準px × intensity / 0.5 × 実幅 / 1080`。時間・SE音量をintensityで勝手に変えない。停止・切り替え・無音整理は0で無効、それ以外は指定した時間・処理で動く。既定値はコーパスの実測分布ではなく、調整可能な設計開始値。

### 時刻

- `at: 4.8`: 全体の秒数。
- `at: {"line":"answer","edge":"start","offset":0.2}`: 発話開始から0.2秒。endも可能。
- `at: {"shot":"detail"}`: ショット開始。end/offsetも可能。
- `at: {"line":"answer","word":"音"}`: 原文と一致する実測文字時刻。対象語が一度だけ現れ、文字境界と時刻が揃う時のみ使用。

at省略時はtarget.line、なければtarget.shotの開始。フレームへ一度丸めて映像・SEで共有する。演出は最低2フレーム。対象ショット・字幕の発話範囲からはみ出す指定はエラー。whipだけはカット点を中心に前後へ配置する。

jump_cut_tightenは発話全体が対象で、at/audioを持たない。params.gapは発話後の間の上限、keepは音声端の余裕、threshold_dbは無音検出閾値。内部の言葉・息継ぎを自動削除せず、元音声キャッシュも変更しない。

### 字幕

常にline.textと同じ本文。ページと改行だけを変え、keywordは単語途中で折らない。標準Intl.Segmenterの日本語語分割を用い、読点の後の句が1行に収まる場合はその手前で改行する。最後が「だ。」「いる。」だけの短いページになる時は、基準文字数の最大1.25倍まで行幅を調整し、必要に応じて文字を縮小する。行数とsafe_areaは維持する。指定時刻の字幕ページに強調語がなければエラー。拡大後の縁取りもsafe_areaを検査し、calloutとの衝突も検出する。

ElevenLabsの文字時刻、またはline.caption_pathのRemotion Caption配列を使用できる。録音には実測時刻を付ける。例:

```json
[
  {"text":"音", "startMs":450, "endMs":800, "timestampMs":null, "confidence":null},
  {"text":"から守る。", "startMs":800, "endMs":2100, "timestampMs":null, "confidence":null}
]
```

連結本文・時刻順序・音声区間内を検査する。AivisSpeechは現環境で文字時刻を返さないため、未添付なら比例分割。at.wordを推測で成立させない。語の強勢との一致は完成音声で確認する。

## 16種の実装範囲

数値範囲・パラメータ一覧はcatalogとJSON Schemaで取得できる。

| 技法 | 基準時間 | 動作・同期 |
|---|---:|---|
| jump_cut_tighten | gap上限0.12s | FFmpegで音声端の実測無音を整理。発話参照から全時間を再確定 |
| caption_pop | 0.14s | 0.86→1.06→1。着地へ同期 |
| keyword_highlight | 0.30s | 原稿内の語を淡黄で強調、短い1.08倍のポップ。開始同期 |
| punch_zoom | 0.20s | 1→1.12→1.05、急加速・収束。収束倍率はショット末尾まで保持。頂点へimpact |
| impact_shake | 0.18s | 14px/0.7度/10Hzのseed付き減衰。実変位から画面端の余白を確保 |
| flash_cut | 0.067s | 不透明度0.8から0へ。カット点同期 |
| freeze_frame | 0.55s | 対象のメディア時計を止め、同じ続きへ再開。ナレーションは継続 |
| broll_cutaway | 1.8s | 指定した実素材を挿入。pushは既定1、明示時のみ緩やかに寄る |
| speed_ramp | 0.35s | FFmpegのsetptsによる単調な時間写像。1→3→1のcosine速度包絡。総尺維持 |
| whip_transition | 0.20s | 実動画を同方向に接続。高速移動＋CSS blur。最大速度付近へ同期 |
| focus_reveal | 0.30s | 16px→0のblur。着地同期 |
| callout | 1.1s | 指定点への線と20文字以内の補足。0.25sで着地し残りは保持 |
| parallax_push | 1.1s | 位置合わせ済みPNG層をdepthに応じて相対移動。層は前後も表示 |
| subject_popout | 0.8s | 被写体の拡大、背景blur/dim、影。着地とSEを同じフレームで確定 |
| rgb_split | 0.12s | 公式EffectsのchromaticAberration。6px基準から収束 |
| glitch_burst | 0.10s | 公式createEffect上の横スライスと色分離。8層・12px基準 |

速度変更は映像だけに適用。ナレーションを自動で早回ししない。前処理の区間・消費した元映像の秒数・時間写像はwork/temporalへ保存。素材不足はエラー。光学フロー補間はv1では行わない。

whipは次のショット開始へ指定し、前後の実素材の余白を検査。総尺を短縮しない。v1では両参加ショットとspeed_ramp/freezeを併用できない。時間加工の誤解釈を避ける明示的な互換制約。

### パターン

| 名前 | 展開 |
|---|---|
| emphasize_claim | punch_zoom + keyword_highlight |
| reveal_shock | punch_zoom + impact_shake + keyword_highlight |
| comic_interrupt | freeze_frame + punch_zoom + keyword_highlight |
| show_evidence | broll_cutaway + caption_pop |
| shift_focus | focus_reveal + callout |
| momentum_transition | whip_transition。速度加工は別ショットへ個別指定 |
| numeric_fact | keyword_highlight + caption_pop |
| isolate_subject | subject_popout + keyword_highlight |

同一atへ展開し、SEは最初の技法に1回だけ付く。reveal_shockに自動flashは入らない。異なる連鎖はeventsに個別の発話・ショット時刻で置く。

## 音

editing.soundsで使用を承認したローカル音源を名前に対応させる。素材本体はGitへ含めない。audio.sfxで選び、同期はstart / peak_velocity / impact / landing / end、追加調整はoffset_ms。

音源のmarkerは、選択したsource_startから何秒後に合わせたいtransientがあるかを表す。`SE開始 = 演出の同期点 - marker + offset_ms`。範囲外のSEは黙って切り落とさずエラー。同一patternで重複させない。FFmpegで3msの立ち上がりと10msの末尾フェードをサンプル単位で前処理する。フレーム単位のvolumeで短いクリックの頭を消さない。音源名だけでtransientを検出したことにはならない。markerは波形と試聴で確認する。

既存audioと同じRemotionミックスへ載せる。style.audio.headroom_db（既定−6dB、範囲−24..0）を声・現場音・SEの全トラックへ適用し、重ねる前に余裕を作る。公式separateAudioToで中間映像MP4とPCMミックスWAVを出力する。AACの中間圧縮による遅延と劣化を避け、FFmpegの2パスloudnorm後に一度だけAACへ変換・結合する。補正前のPCMと完成AACを実測し、true peakが−0.5 dBTPを超えた場合はエラー。目標は−16 LUFS / −1.5 dBTP。元から歪んだ音源を修復する機能ではない。

## 制約と環境

policy.strong_effect_cooldown（既定2s）、max_per_10s、never_stackはreviewに警告する。密度を創作の合否には使わない。同じ対象の同技法の重複、空白・素材不足、無効参照、字幕の不一致、宣言した被写体の見切れはエラー。

通常はrenderer=cpu。rgb/glitchはwebglを明示し、RemotionへANGLEを渡して同時実行数1で描画する。使用不能なら失敗させ、演出なしの成功を返さない。この設定はローカルworkerの動作であり、分散・クラウドGPUジョブ基盤は未実装。

parallax/popoutのv1は静止画の背景と同寸法・位置合わせ済み透過PNGが必要。アルファチャンネルだけでなく実際の透明部分と被写体を検証する。原画に被写体が残っていると二重になるため背景plateを用意し、各層の構図を確認する。

`@remotion/video-matting`は現環境の公開npmで取得できず、本体も4.0.521へ固定。自動動画マッティング、WebGPU動画層、Three.jsの3D、方向性ブラー専用shaderは実装済みとして扱わない。追加時も素材契約と実レンダー回帰を更新する。

## 更新の検証

preview→review→修正→final。演出前後を再生し、同一原音声の比較版も見る。数値既定値を変更する時はregistryと評価をセットで更新し、JSON Schemaを再生成する。

examples/create_editing_fixture.pyとtests/verify_editing_render.pyは16種を実行する工学的なfixture。停止・再開、速度写像の途中と末尾、透過層の継続、音声端の余裕、完成音量、38時点の画像参照を検証。素材・フォント・依存版が変わる場合は差を確認して参照を明示更新する。画像の一致は人手編集に対する優位性の証明ではない。
