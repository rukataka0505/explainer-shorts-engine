# 採用した知見と設計判断

確認日: 2026-09-07。出典の推奨と、このエンジンでの判断を分けて記す。

| 一次資料・公式資料 | 根拠にした点 | 実装・運用への反映 |
|---|---|---|
| [YouTube: Todd ShermanとJenny HoyosのShorts対談](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/) | 最初の瞬間のフック、短い中にも小さな物語。成功クリエイターの実務知見であり因果実験ではない | 実写の動作から始め、一つの疑問を回収する構成。秒数の一律強制はしない |
| [Adobe: J/Lカット](https://helpx.adobe.com/premiere/desktop/edit-projects/trim-clips/perform-j-cuts-and-l-cuts.html) | 映像と音の編集点をずらす編集手法 | 音声・映像の独立タイムライン、任意の発話に対するオフセット |
| [Remotion公式Agent Skills](https://www.remotion.dev/docs/ai/skills) / [ソース](https://github.com/remotion-dev/skills) | フレームに基づく決定的な描画、公式メディア部品、音声トリムと音量コールバック | @remotion/media、Sequence、フレーム時間、公式スキルの同梱。スキル本文は改変せず保存 |
| [PySceneDetect](https://www.scenedetect.com/docs/latest/) | AdaptiveDetector、既存シーン検出API | ソース候補の時刻と画像一覧。意味の自動評価は作らない |
| [FFmpeg loudnorm](https://ffmpeg.org/ffmpeg-filters.html#loudnorm) | EBU R128の測定、2パス正規化、true peak制御 | 実測から全体を正規化し、映像はコピー。完成AACも再測定 |

公式Remotionスキルの固定版: `remotion-dev/skills@f54682712abc4a68cdc7c41513bd3b3298829873`、スキルversion `4.0.521`。この版の動画ページに「秒」と`2 * fps`が混在する箇所があるため、実装はインストール済みAPI型と実レンダーで確認したフレーム単位を使う。

RemotionのStudioでJSXへドラッグ編集を書き戻す場合の規則と、データ駆動レンダーは用途が異なる。このエンジンはproject.jsonを正本とし、コンパイルしたショットを描画する。独自のドラッグエディターや別の編集言語は実装しない。

## 継承と変更

元エンジン: `video-production-automation-engine@cab13943e8c19b1577a5a104b3450372a20f9bd4`。

音声キャッシュ、Windowsでの背景ジョブと子プロセス管理、メディア検査、非公開YouTube納品を再利用した。映像と音をbeat内に固定していた部分は全体の編集時間軸へ変更。図解、字幕、立ち絵、口パクは今回の映像方針に不要なので外した。レンダーはRemotion一本に保ち、PySceneDetectとFFmpegを素材選択・検査に使う。

Remotionはソース公開のライセンス製品で、一般的な無条件のOSSと同一ではない。[公式ライセンス](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md)を参照。個人利用では利用可能な範囲を確認して採用した。新規の素材解析器や外部LLM呼び出し基盤を増やす必要はない。

## 品質をどう扱うか

コードのテストは時間・構図の計算と破損を検証する。カットの良さや再生数は証明しない。実写サンプルは実装の動作と編集判断をレビューするためのもの。異なる題材でも素材確認→編集→視聴修正を繰り返す。自称の「人間レベルスコア」を合否に使わない。
