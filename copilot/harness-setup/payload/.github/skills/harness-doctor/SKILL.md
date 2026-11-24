---
name: harness-doctor
description: ハーネス自体の健康診断を行う。hooks の未登録、TASK.md の破損、制御文字、文脈ファイルの文字数超過、INDEX のずれなどを検査し、結果の読み方を示す。「doctor を実行」「ハーネスが壊れていないか確認」と頼まれたとき、または sessionStart hook の出力に doctor の NG/WARN が出たときに使う。
---

# harness-doctor

## 実行

```bash
python3 _harness/scripts/doctor.py           # 全件（INFO を含む）
python3 _harness/scripts/doctor.py --quiet   # NG と WARN だけ
python3 _harness/scripts/doctor.py --selftest  # わざと壊した状態で検出できるかを確かめる
```

NG があれば exit 1。各行は `レベル  何が  どこで  どうすればよいか`。

## 読み方

- **NG**: 今すぐ直す。完了判定や記録が信用できない状態（hook 未登録、規約ファイルの欠落、frontmatter 破損、制御文字、常に読む層の上限超過、verify 未設定、done なのに verify が pass でない）。
- **WARN**: 近いうちに直す（放置タスク、文脈ファイルの肥大、INDEX のずれ、タスクなしのセッション、hook のエラー）。
- **INFO**: 件数などの参考情報。

## 方針

- doctor は**報告だけ**で、自動では直さない。直すかどうかは、結果をユーザーに見せて一緒に決める。
- INDEX のずれは `python3 _harness/scripts/build_index.py` で直る（自動生成ファイルなので安全）。
- 「異常なし」は、検査範囲の中で異常がないという意味にすぎない。文書どうしの矛盾や PROFILE の内容の正しさは検査しない。
- 新しい種類の故障に出会ったら、検査項目を `_harness/scripts/doctor.py` に足す（テストも `_harness/tests/test_doctor.py` に足す）。
