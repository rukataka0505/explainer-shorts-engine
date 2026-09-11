# 音の設計・SE棚

通常制作では台本・主要ショットと一緒に、各beatの現場音、SE、音楽、静けさの役割を決める。映像側の音はミュートされる。音の採用は必ず `audio` または `editing.events[].audio` へ書く。音源の登録だけでは鳴らない。

## 1. 台本の段階で採否を残す

```powershell
.\.venv\Scripts\python.exe tools/video.py sound-plan projects/<案件> --init
```

正本に `sound_design` の下書きを追加する。既存の設計は上書きしない。これは編集者のメモであり、新しい再生言語ではない。音を自動配置・自動消音しない。

```json
{
  "sound_design": {
    "version": 1,
    "beats": [{
      "beat": "hook",
      "ambience": {"decision": "use", "reason": "wideショットの放水を現場音で伝える", "refs": ["audio:water"]},
      "sfx": {"decision": "use", "reason": "答えの発見だけ短く強調", "refs": ["event:sound-reveal"]},
      "music": {"decision": "omit", "reason": "水の音と声を優先する", "refs": []},
      "silence": {"decision": "omit", "reason": "水の連続音で次のカットへつなぐ", "refs": []}
    }]
  }
}
```

`use` は採用、`omit` は意図的な不採用、`pending` は未決定。beatごとに4役の採否と理由を記す。複数ショットでは理由に対象ショットと音の変化を記し、必要な音をrefsへ列挙する。`audio:water` は `audio` の `id:water`、`event:sound-reveal` はSEを持つ既存演出のID。静けさを採用する場合は理由に区間・対象トラックを記し、実際の `audio.from/to` やフェード、声のgapで空間を作る。全トラックの自動ミュートを意味しない。

```powershell
.\.venv\Scripts\python.exe tools/video.py sound-plan projects/<案件>
```

未決定・beat漏れ・理由未記入・採用音の参照漏れ・無効な参照を表示する。prepare/buildとreviewにも出る。警告は制作を強制停止しない。意図的にSEなしの作品は正当であり、SE本数をノルマにしない。

## 2. 小さな棚から検索・試聴して取り込む

```powershell
.\.venv\Scripts\python.exe tools/video.py sounds --query 確認
.\.venv\Scripts\python.exe tools/video.py sounds --audition
.\.venv\Scripts\python.exe tools/video.py sounds projects/<案件> --use kenney_click_001
```

試聴棚は `.cache/sounds/index.html`。用途で絞って一音ずつ再生できる。24音の原音は [Kenney Interface Sounds](https://kenney.nl/assets/interface-sounds)、取得先は固定リビジョンの [WAV配布](https://github.com/Calinou/kenney-interface-sounds)。クリック・確認・疑問・否定・強調・展開・中断の編集用アクセントを揃えた。記録映像の現場音の代替にはしない。

`editing/sounds.v1.json` に用途、取得先、SHA256、尺、ピーク、marker候補、初期音量を保存。音源本体はGitに入れず、再取得できる。24音ともデコード・非無音検査済み。**主観的な試聴・場面への適合性は未確認**であり、試聴済みライブラリとは呼ばない。markerは最大振幅の候補で、強勢や着地の知覚とは限らない。採用時の試聴で調整する。

取り込みは `assets/sfx/` へコピーして読み戻し、`editing.sounds` に登録する。既存の異なる設定・音源は上書きしない。再実行可能。登録後、既存演出に `"audio":{"sfx":"kenney_click_001","sync":"impact"}` などを付ける。音だけを使いたい場合は `audio` に区間を明示する。SEのためだけに不要な映像演出を足さない。

初期音量は原音ピークを目安にした控えめな開始値。完成ミックスの正規化は声とSEの相対音量を改善しない。声に埋もれる場合はSEのvolume・時刻・音色または現場音のduckを調整する。

## 3. プレビューで確かめる

prepare前に採用音を正本へ配置し、`sound-plan` の未決定を解消する。通常のpreview→reviewでSE前後を音付き再生し、意味・声の聞き取り・耳当たり・着地を確認してからfinalへ進む。試聴していなければその旨を残す。ライブラリの試聴と完成ミックスの確認は別工程。

音経路の工学的な回帰確認は `tests/` の機械検査で行う。作品固有の台本・完成動画・音配置を検証用テンプレートとして残さず、通常案件ではpreview→reviewの試聴で場面への適合と聞こえ方を判断する。
